import json
from typing import Literal
from .state import RAGState

class PolicyAgent:
    def __init__(self, client):
        self.client = client
        self.model = "claude-sonnet-4-5-20250929"

    def decide(self, state: RAGState) -> Literal["CONTINUE", "FINISH", "REVISE_PLAN"]:
        """
        Evaluate progress and decide next action.
        """
        prompt = f"""
        Original Question: "{state['original_question']}"
        
        Research completed so far:
        {self._format_research_summary(state['past_steps'])}
        
        Remaining planned steps: {len(state['plan']) - state['current_step_index']}
        Iterations used: {state['iteration_count']} / {state['max_iterations']}
        
        Decision options:
        - CONTINUE: Execute next planned step
        - FINISH: Sufficient information gathered, generate answer
        - REVISE_PLAN: Current plan won't work, need different approach
        
        CRITICAL: Set "needs_external_enrichment": true if the research findings contain specific entities, technical terms, or claims that could be enriched with external data (specs, news, definitions, side effects), AND you haven't done a web search yet.
        
        Return ONLY a JSON object: {{"decision": "CONTINUE|FINISH|REVISE_PLAN", "reasoning": "...", "needs_external_enrichment": true|false}}
        """
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        try:
            if hasattr(response.content[0], 'text'):
                content = response.content[0].text.strip()
            else:
                 content = str(response.content).strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            decision_data = json.loads(content)
            decision = decision_data.get("decision", "CONTINUE")
            
            # Programmatic Check: Force REVISE_PLAN if external enrichment is needed but no web search
            # This ensures we enrich personal notes with external data
            
            # Check if we have done a web search
            has_web_search = any(
                step.get('step', {}).get('search_strategy') == 'web'
                for step in state.get('past_steps', [])
            )
            
            # Check if we have a PLANNED web search remaining
            remaining_steps = state.get('plan', [])[state.get('current_step_index', 0):]
            has_planned_web = any(step.get('search_strategy') == 'web' for step in remaining_steps)
            
            if decision_data.get("needs_external_enrichment") and not has_web_search and not has_planned_web and decision == "FINISH":
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
