import json
import os
from typing import Literal
from .state import RAGState
from .supervisor import RetrievalSupervisor
from .utils.universal_client import extract_response_text

class PolicyAgent:
    def __init__(self, client):
        self.client = client
        self.model = "claude-sonnet-4-5-20250929"

    @staticmethod
    def _truncate_text(value: str, limit: int) -> str:
        text = str(value or "")
        if len(text) <= limit:
            return text
        return text[: max(limit - 16, 0)].rstrip() + "\n... [truncated]"

    def decide(self, state: RAGState) -> Literal["CONTINUE", "FINISH", "REVISE_PLAN"]:
        """
        Evaluate progress and decide next action.
        """
        provider = getattr(self.client, "provider", "").lower()
        summary_limit = int(
            os.getenv(
                "DEEP_THINKING_LMSTUDIO_POLICY_SUMMARY_CHARS"
                if provider in ("lmstudio", "mlx")
                else "DEEP_THINKING_POLICY_SUMMARY_CHARS",
                os.getenv("DEEP_THINKING_MLX_POLICY_SUMMARY_CHARS", "2500")
                if provider in ("lmstudio", "mlx")
                else "6000",
            )
        )
        research_summary = self._truncate_text(self._format_research_summary(state['past_steps']), summary_limit)
        query_profile = RetrievalSupervisor.build_query_profile(state.get("original_question", ""))

        prompt = f"""
        Original Question: "{state['original_question']}"
        
        Research completed so far:
        {research_summary}
        
        Remaining planned steps: {len(state['plan']) - state['current_step_index']}
        Iterations used: {state['iteration_count']} / {state['max_iterations']}
        
        Decision options:
        - CONTINUE: Execute next planned step
        - FINISH: Sufficient information gathered, generate answer
        - REVISE_PLAN: Current plan won't work, need different approach
        
        Query profile:
        - needs_external_authority: {query_profile.get("needs_external_authority")}
        - requires_current_information: {query_profile.get("requires_current_information")}
        - needs_authoritative_sources: {query_profile.get("needs_authoritative_sources")}
        - prefers_reasoning_first: {query_profile.get("prefers_reasoning_first")}

        CRITICAL: Set "needs_external_enrichment": true only when the answer still requires current or authoritative external information that has not been retrieved yet. Do not set it true merely because the question contains technical vocabulary or named entities.
        
        Return ONLY a JSON object: {{"decision": "CONTINUE|FINISH|REVISE_PLAN", "reasoning": "...", "needs_external_enrichment": true|false}}
        """
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=200 if provider in ("lmstudio", "mlx") else 300,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        try:
            content = extract_response_text(response)
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            decision_data = json.loads(content)
            decision = decision_data.get("decision", "CONTINUE")
            remaining_steps = state.get('plan', [])[state.get('current_step_index', 0):]

            if (
                query_profile.get("is_summary_request")
                and state.get("summary_intent") == "broad"
                and remaining_steps
                and decision == "FINISH"
            ):
                return "CONTINUE"
            
            # Programmatic Check: Force REVISE_PLAN if external enrichment is needed but no web search
            # This ensures we enrich personal notes with external data
            
            # Check if we have done a web search
            has_web_search = any(
                step.get('step', {}).get('search_strategy') == 'web'
                for step in state.get('past_steps', [])
            )
            
            # Check if we have a PLANNED web search remaining
            has_planned_web = any(step.get('search_strategy') == 'web' for step in remaining_steps)
            
            if (
                decision_data.get("needs_external_enrichment")
                and not query_profile.get("prefers_vault_only_summary")
                and query_profile.get("needs_external_authority")
                and not has_web_search
                and not has_planned_web
                and decision == "FINISH"
            ):
                print("⚠️ Policy: External enrichment needed but no web search. Forcing REVISE_PLAN.")
                return "REVISE_PLAN"
            
            # Validate decision
            if decision not in ["CONTINUE", "FINISH", "REVISE_PLAN"]:
                return "CONTINUE"
                
            return decision
        except Exception as e:
            print(f"Error parsing policy decision: {e}")
            return "CONTINUE"

    def _format_research_summary(self, past_steps):
        summary = ""
        for ps in past_steps:
            summary += f"- Step {ps['step']['step_number']}: {ps['key_findings']} (Conf: {ps['confidence']})\n"
        return summary
