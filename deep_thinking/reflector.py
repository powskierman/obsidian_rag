import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Any
from .state import Step, PastStep, RAGState

class ReflectionAgent:
    def __init__(self, client):
        self.client = client
        self.model = "claude-sonnet-4-5-20250929"

    def reflect(self, step: Step, documents: List[Dict[str, Any]], state: RAGState) -> PastStep:
        """
        Summarize findings from the current step into a single insight.
        """
        # Format documents for prompt
        doc_text = ""
        for i, doc in enumerate(documents[:5]): # Limit to top 5 to save tokens
            doc_text += f"--- Document {i+1} ---\n"
            # Allow up to 100,000 chars per doc to support full file expansion
            doc_text += f"Content: {doc.get('content', '')[:100000]}\n\n"

        prompt = f"""
        Research Step: "{step['sub_question']}"
        
        Retrieved {len(documents)} documents.
        
        Document snippets:
        {doc_text}
        
        Previous findings:
        {self._format_past_steps(state['past_steps'])}
        
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
            max_tokens=500,
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
