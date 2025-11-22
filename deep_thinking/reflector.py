import json
from typing import List, Dict, Any
from .state import Step, PastStep, RAGState

class ReflectionAgent:
    def __init__(self, anthropic_client):
        self.client = anthropic_client
        self.model = "claude-sonnet-4-5"

    def reflect(self, step: Step, documents: List[Dict[str, Any]], state: RAGState) -> PastStep:
        """
        Summarize findings from the current step into a single insight.
        """
        # Format documents for prompt
        doc_text = ""
        for i, doc in enumerate(documents[:5]): # Limit to top 5 to save tokens
            doc_text += f"--- Document {i+1} ---\n"
            doc_text += f"Source: {doc.get('source', 'Unknown')}\n"
            doc_text += f"Content: {doc.get('content', '')[:500]}...\n\n" # Truncate content

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
            messages=[{"role": "user", "content": prompt}]
        )
        
        try:
            content = response.content[0].text.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            reflection = json.loads(content)
            
            return PastStep(
                step=step,
                documents_found=len(documents),
                key_findings=reflection.get("key_findings", "No clear findings."),
                confidence=reflection.get("confidence", 0.0)
            )
        except Exception as e:
            print(f"Error parsing reflection: {e}")
            return PastStep(
                step=step,
                documents_found=len(documents),
                key_findings="Error analyzing results.",
                confidence=0.0
            )

    def _format_past_steps(self, past_steps: List[PastStep]) -> str:
        summary = ""
        for ps in past_steps:
            summary += f"Step {ps['step']['step_number']}: {ps['step']['sub_question']}\n"
            summary += f"Finding: {ps['key_findings']}\n\n"
        return summary
