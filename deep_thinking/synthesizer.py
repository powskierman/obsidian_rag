import json
import re
from typing import List, Tuple
from .state import RAGState

class FinalAnswerGenerator:
    def __init__(self, client, model="moonshotai/kimi-k2-0905"):
        self.client = client
        self.model = model

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
        
        You are an expert Research Assistant. Generate a high-quality, comprehensive report.
        
        REQUIREMENTS:
        1. **Structure**: Start with an "## Executive Summary". Use `##` and `###` headers for all sections.
        2. **Formatting**: Use standard Markdown only. 
           - Use **Markdown Tables** for any comparison data (timeline, scan results, etc.).
           - bold **key terms**.
           - Do NOT use ascii lines like `----` or `____`. 
        3. **Content**:
           - Directly address the original question.
           - Synthesize findings from search steps.
           - Cite vault sources as `[[Folder/Note Name]]`.
           - Cite web sources as `[Title](URL)`.
        4. **Web Findings**: If web results are present, you MUST add a `## Web Context` section explaining any technical terms, definitions, or external context found in the web results.
        5. **Images**: Embed relevant images if available: `![Description](image_url)`.
        
        Output Format (XML + JSON):
        
        <formatted_answer>
        ## Executive Summary
        (Brief overview...)
        
        ## Detailed Analysis
        (Your content with tables...)
        
        ## Web Context
        (If applicable...)
        </formatted_answer>
        
        <metadata_json>
        {{
            "citations": [["[[Note Name]]", "URL"], ...],
            "confidence_score": 0.9,
            "confidence_justification": "Detailed scan results found..."
        }}
        </metadata_json>
        """
        
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        try:
            content = response.choices[0].message.content.strip()
            
            # Extract formatted answer
            answer_match = re.search(r'<formatted_answer>(.*?)</formatted_answer>', content, re.DOTALL)
            answer = answer_match.group(1).strip() if answer_match else "Could not parse answer from response."
            
            # Extract and parse metadata JSON
            metadata_match = re.search(r'<metadata_json>(.*?)</metadata_json>', content, re.DOTALL)
            metadata = {}
            if metadata_match:
                try:
                    metadata_str = metadata_match.group(1).strip()
                    if metadata_str.startswith("```json"):
                        metadata_str = metadata_str[7:]
                    if metadata_str.endswith("```"):
                        metadata_str = metadata_str[:-3]
                    metadata = json.loads(metadata_str.strip())
                except:
                    pass
            
            return {
                "answer": answer,
                "citations": metadata.get("citations", []),
                "confidence_score": metadata.get("confidence_score", 0.0),
                "confidence_justification": metadata.get("confidence_justification", "No justification provided.")
            }
        except Exception as e:
            print(f"Error generating final answer: {e}")
            return {
                "answer": f"Error generating answer: {content[:200]}...",
                "citations": [],
                "confidence_score": 0.0,
                "confidence_justification": f"Error: {e}"
            }
