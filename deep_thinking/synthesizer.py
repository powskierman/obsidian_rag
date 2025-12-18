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
        vault_docs = ""
        web_docs = ""
        image_urls = []
        
        for i, doc in enumerate(state['retrieved_documents']):
            source = doc.get('source', 'Unknown')
            content = doc.get('content', '')[:300]
            
            # Collect images from web results
            if 'images' in doc and doc['images']:
                image_urls.extend(doc['images'])
            
            if doc.get('type') == 'web':
                web_docs += f"[{i+1}] WEB: {source}\nContent: {content}...\n\n"
            else:
                vault_docs += f"[{i+1}] VAULT: {source}\nContent: {content}...\n\n"

        # Build image section for prompt
        images_section = ""
        if image_urls:
            images_section = f"\n        Relevant Images Found:\n"
            for idx, img_url in enumerate(image_urls[:5]):  # Limit to top 5 images
                images_section += f"        - Image {idx+1}: {img_url}\n"
        
        prompt = f"""
        Original question: "{state['original_question']}"
        
        Research summary:
        {state['accumulated_context']}
        
        Vault Documents:
        {vault_docs}
        
        Web Search Results:
        {web_docs}
        {images_section}
        
        Generate a comprehensive answer that:
        1. Directly addresses the original question
        2. Synthesizes findings from all research steps
        3. Cites vault sources using Obsidian link format: [[Folder/Note Name]]
        4. Cites web sources as [URL](URL) or [Title](URL)
        5. You MUST include a separate "## Web Findings" section if any web search results are provided. Use this section to explain standard medical definitions, treatments, or external context found in the web results, even if they are general.
        6. If images are provided above, embed relevant ones using markdown format: ![Description](image_url)
           - For hardware/wiring questions, prioritize pinout diagrams and wiring schematics
           - Place images in appropriate sections (e.g., under "Hardware Connection" or "Wiring Diagram")
        7. Acknowledges any gaps or uncertainties
        
        Return ONLY a JSON object:
        {{
            "answer": "...",
            "citations": [["[[Medical/CAR-T/Treatment Log 2023-05-15]]", "https://example.com"],
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
