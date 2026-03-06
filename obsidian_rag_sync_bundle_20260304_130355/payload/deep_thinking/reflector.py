import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Any
from .state import Step, PastStep, RAGState

class ReflectionAgent:
    def __init__(self, client):
        self.client = client
        self.model = "claude-sonnet-4-5-20250929"

    @staticmethod
    def _provider_limits(provider: str) -> tuple[int, int, int]:
        provider = (provider or "").lower()
        if provider == "mlx":
            return (
                int(os.getenv("DEEP_THINKING_MLX_REFLECT_DOCS", "3")),
                int(os.getenv("DEEP_THINKING_MLX_REFLECT_DOC_CHARS", "2000")),
                int(os.getenv("DEEP_THINKING_MLX_REFLECT_PAST_CHARS", "2500")),
            )
        return (
            int(os.getenv("DEEP_THINKING_REFLECT_DOCS", "5")),
            int(os.getenv("DEEP_THINKING_REFLECT_DOC_CHARS", "12000")),
            int(os.getenv("DEEP_THINKING_REFLECT_PAST_CHARS", "6000")),
        )

    @staticmethod
    def _truncate_text(value: str, limit: int) -> str:
        text = str(value or "")
        if len(text) <= limit:
            return text
        return text[: max(limit - 16, 0)].rstrip() + "\n... [truncated]"

    def reflect(self, step: Step, documents: List[Dict[str, Any]], state: RAGState) -> PastStep:
        """
        Summarize findings from the current step into a single insight.
        """
        provider = getattr(self.client, "provider", "").lower()
        max_docs, doc_char_limit, past_char_limit = self._provider_limits(provider)

        # Format documents for prompt
        doc_text = ""
        for i, doc in enumerate(documents[:max_docs]):
            doc_text += f"--- Document {i+1} ---\n"
            doc_text += f"Content: {self._truncate_text(doc.get('content', ''), doc_char_limit)}\n\n"

        previous_findings = self._truncate_text(self._format_past_steps(state['past_steps']), past_char_limit)

        prompt = f"""
        Research Step: "{step['sub_question']}"
        
        Retrieved {len(documents)} documents.
        
        Document snippets:
        {doc_text}
        
        Previous findings:
        {previous_findings}
        
        Provide:
        1. One-sentence summary of key finding
        2. Confidence score (0.0-1.0) on answer completeness
        3. Are there gaps that need another search?
        
        Return ONLY a JSON object with this format:
        {{
            "key_findings": "...",
            "confidence": 0.8,
            "has_gaps": false
        }}
        """
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=250 if provider == "mlx" else 500,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        try:
            if hasattr(response.content[0], 'text'):
                content = response.content[0].text.strip()
            else:
                 content = str(response.content).strip()
            # Robust JSON extraction
            start_idx = content.find('{')
            end_idx = content.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                json_str = content[start_idx:end_idx+1]
                reflection = json.loads(json_str)
            else:
                raise ValueError("No JSON object found in response")
            
            return PastStep(
                step=step,
                documents_found=len(documents),
                key_findings=reflection.get("key_findings", "No clear findings."),
                confidence=reflection.get("confidence", 0.0)
            )
        except Exception as e:
            self._log_debug("Reflection parse error", {"error": str(e), "response": content[:1000] if content else ""})
            key_findings = self._fallback_key_findings(documents)
            return PastStep(
                step=step,
                documents_found=len(documents),
                key_findings=key_findings,
                confidence=0.0
            )

    def _format_past_steps(self, past_steps: List[PastStep]) -> str:
        summary = ""
        for ps in past_steps:
            summary += f"Step {ps['step']['step_number']}: {ps['step']['sub_question']}\n"
            summary += f"Finding: {ps['key_findings']}\n\n"
        return summary

    @staticmethod
    def _fallback_key_findings(documents: List[Dict[str, Any]]) -> str:
        if not documents:
            return "No documents retrieved for this step."
        sources = []
        for doc in documents[:3]:
            source = doc.get("source") or "Unknown"
            sources.append(source)
        source_text = ", ".join(sources)
        return f"Retrieved {len(documents)} documents. Top sources: {source_text}."

    @staticmethod
    def _log_debug(message: str, details: Dict[str, Any]) -> None:
        log_path = os.getenv("DEEP_THINKING_LOG_PATH", "/tmp/deep_thinking.log")
        try:
            log_dir = os.path.dirname(log_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": message,
                "details": details
            }
            with open(log_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload) + "\n")
        except Exception:
            pass
