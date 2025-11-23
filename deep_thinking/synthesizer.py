import json
from typing import List, Tuple
from .state import RAGState

class FinalAnswerGenerator:
    def __init__(self, anthropic_client):
        self.client = anthropic_client
        self.model = "claude-sonnet-4-5"

    def generate(self, state: RAGState) -> Tuple[str, List[str]]:
        """
        Synthesize final answer with Obsidian-style citations.
        """
        # Format documents for citation
        doc_text = ""
        for i, doc in enumerate(state['retrieved_documents']):
            doc_text += f"[{i+1}] {doc.get('source', 'Unknown')}: {doc.get('content', '')[:300]}...\n"

        prompt = f"""
        Original question: "{state['original_question']}"
        
        Research summary:
        {state['accumulated_context']}
        
        All retrieved documents:
        {doc_text}
        
        Generate a comprehensive answer that:
        1. Directly addresses the original question
        2. Synthesizes findings from all research steps
        3. Cites sources using Obsidian link format: [[Folder/Note Name]]
        4. Acknowledges any gaps or uncertainties
        
        Return ONLY a JSON object:
        {{
            "answer": "...",
            "citations": ["[[Medical/CAR-T/Treatment Log 2023-05-15]]", "[[Tech/ESP32/Specs]]"],
            "confidence_score": 0.9,
            "confidence_justification": "Detailed scan results found..."
        }}
        """
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        try:
            content = response.content[0].text.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            result = json.loads(content)
            return {
                "answer": result.get("answer", "Could not generate answer."),
                "citations": result.get("citations", []),
                "confidence_score": result.get("confidence_score", 0.0),
                "confidence_justification": result.get("confidence_justification", "No justification provided.")
            }
        except Exception as e:
            print(f"Error generating final answer: {e}")
            return {
                "answer": "Error generating answer.",
                "citations": [],
                "confidence_score": 0.0,
                "confidence_justification": f"Error: {e}"
            }
