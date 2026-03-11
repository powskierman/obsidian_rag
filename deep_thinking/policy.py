import json
import os
import re
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

    @staticmethod
    def _is_web_locator(value: str) -> bool:
        text = str(value or "").strip().lower()
        return text.startswith("http://") or text.startswith("https://")

    @classmethod
    def _prefers_vault_first(cls, question: str) -> bool:
        lowered = str(question or "").lower()
        patterns = (
            r"\b(?:my|our)\s+(?:notes?|vault|documents?|files?|logs?|pdfs?|reports?)\b",
            r"\b(?:in|from)\s+(?:my|our)\s+vault\b",
            r"\b(?:these|those)\s+notes\b",
            r"\bmy\s+vault\b",
            r"\bvault\b",
            r"\bnotes\b",
        )
        return any(re.search(pattern, lowered) for pattern in patterns)

    @classmethod
    def _has_vault_evidence(cls, state: RAGState) -> bool:
        for doc in state.get("retrieved_documents", []) or []:
            if not RetrievalSupervisor._is_citable_doc(doc):
                continue
            source_category = str(doc.get("source_category") or "").strip().lower()
            locator = str(
                doc.get("filepath")
                or doc.get("source")
                or doc.get("url")
                or doc.get("filename")
                or ""
            ).strip()
            if source_category == "web" or cls._is_web_locator(locator):
                continue
            return True
        return False

    @classmethod
    def _has_substantive_vault_evidence(cls, state: RAGState) -> bool:
        thin_patterns = (
            r"^on explicit graph path\b",
            r"^context:\s.+\bmentioned\.?$",
        )
        for doc in state.get("retrieved_documents", []) or []:
            if not RetrievalSupervisor._is_citable_doc(doc):
                continue
            source_category = str(doc.get("source_category") or "").strip().lower()
            locator = str(
                doc.get("filepath")
                or doc.get("source")
                or doc.get("url")
                or doc.get("filename")
                or ""
            ).strip()
            if source_category == "web" or cls._is_web_locator(locator):
                continue

            source_type = str(doc.get("source_type") or "").strip().lower()
            text = re.sub(r"\s+", " ", str(doc.get("content") or doc.get("snippet") or "").strip())
            if not text:
                continue
            lowered = text.lower()
            if any(re.match(pattern, lowered) for pattern in thin_patterns):
                continue
            if source_type == "entity-context" and len(text) < 160:
                continue
            if len(text) < 80:
                continue
            return True
        return False

    @staticmethod
    def _has_planned_vault_step(steps) -> bool:
        vault_strategies = {"vector", "hybrid", "graph", "graph-local", "graph-global"}
        return any(step.get("search_strategy") in vault_strategies for step in (steps or []))

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
            prefers_vault_first = self._prefers_vault_first(state.get("original_question", ""))
            has_vault_evidence = self._has_vault_evidence(state)
            has_substantive_vault_evidence = self._has_substantive_vault_evidence(state)
            has_planned_vault = self._has_planned_vault_step(remaining_steps)

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

            # Personal/vault-scoped questions must not finish on web-only evidence.
            if decision == "FINISH" and prefers_vault_first and (not has_vault_evidence or not has_substantive_vault_evidence):
                if has_planned_vault:
                    print("⚠️ Policy: Vault-scoped query still has a pending vault step. Forcing CONTINUE.")
                    return "CONTINUE"
                print("⚠️ Policy: Vault-scoped query lacks substantive vault evidence. Forcing REVISE_PLAN.")
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
