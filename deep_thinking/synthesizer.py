import json
import os
import re
from typing import List, Tuple
from .state import RAGState
try:
    from src.utils.prompt_builder import build_prompt_appendix, build_provider_guardrails
except ImportError:
    try:
        from utils.prompt_builder import build_prompt_appendix, build_provider_guardrails
    except ImportError:
        def build_prompt_appendix(user_query: str, provider: str) -> str:
            return ""
        def build_provider_guardrails(provider: str) -> str:
            return ""

class FinalAnswerGenerator:
    def __init__(self, client):
        self.client = client
        self.model = "claude-sonnet-4-5-20250929"

        # Try to load user profile from mem0 for system prompt
        user_profile_text = ""
        try:
             # Importing here to avoid circular imports if any
             from src.utils.memory_manager import get_memory_manager
             mem_manager = get_memory_manager()
             if mem_manager:
                 # Get all memories to build a profile
                 all_memories = mem_manager.get_all_memories()
                 if all_memories:
                     # Filter for relevant facts if needed, or take top N
                     facts = [m.get('text', '') for m in all_memories if isinstance(m, dict)]
                     # Limit to top 20 facts to avoid context bloat
                     if facts:
                         user_profile_text = "\n\nUser Profile & Preferences:\n" + "\n".join([f"- {f}" for f in facts[:20]])
        except Exception:
             pass

        # Michel's custom system prompt for compassionate, personalized responses
        self.system_prompt = f"""You are a **Deep Thinking AI assistant** integrated with Michel's Obsidian Knowledge Base.
{user_profile_text}

Your task is to answer questions by analyzing the retrieved materials and Michel's personal context.

When generating your answer:
1. Reference Michel's specific **medical timeline** (DLBCL, Yescarta, scans) when relevant.
2. Incorporate insights from his **Obsidian notes**, citing which notes or sources you use.
3. Maintain a **compassionate and supportive** tone for medical topics.
4. Provide **technical depth** and precision for engineering and coding topics.
5. Adapt to his **expert-level understanding** — avoid overexplaining known concepts.
6. Be **concise but thorough**, focusing on clarity and reasoning.
7. Avoid redundant or generic phrasing.

Finally, provide your answer in a structured, easy-to-read format."""

    def generate(self, state: RAGState) -> Tuple[str, List[str]]:
        """
        Synthesize final answer with Obsidian-style citations.
        """
        # Format documents for citation
        vault_docs = ""
        web_docs = ""
        image_urls = []
        
        # Priority 1: Use Raw Context Buffer if available (high fidelity)
        raw_buffer = state.get("raw_context_buffer", [])
        if raw_buffer:
            for i, item in enumerate(raw_buffer):
                source = item.get("source", "Unknown")
                # Context buffer has full text, usually truncated naturally by retrieval or reasonable limit
                # We typically allow more here than the standard loop
                content = item.get("content", "")[:2000] 
                
                if "http" in source and not "localhost" in source:
                    web_docs += f"[{i+1}] WEB: {source}\nContent: {content}\n\n"
                else:
                    vault_docs += f"[{i+1}] VAULT: {source}\nContent: {content}\n\n"
                    
        # Priority 2: Fallback to standard retrieved_documents (if buffer empty)
        else:
            for i, doc in enumerate(state['retrieved_documents']):
                source = doc.get('source', 'Unknown')
                content = doc.get('content', '')[:500] # Increased from 300
                
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
        4. Cites web sources using markdown links with the ACTUAL page title from the web results (NOT the word "Title"): [Actual Page Title](https://example.com)
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

        provider = getattr(self.client, "provider", "").lower()
        prompt_appendix = build_prompt_appendix(state["original_question"], provider)
        if prompt_appendix:
            prompt = f"{prompt}\n\n{prompt_appendix}\n"

        max_tokens = int(os.getenv("DEEP_THINKING_MAX_TOKENS", "4096"))
        if provider == "claude":
            max_tokens = int(os.getenv("DEEP_THINKING_CLAUDE_MAX_TOKENS", "8192"))
        if provider in ("chatgpt", "openai"):
            max_tokens = int(os.getenv("DEEP_THINKING_OPENAI_MAX_TOKENS", str(max_tokens)))

        system_prompt = self.system_prompt
        guardrails = build_provider_guardrails(provider)
        if guardrails:
            system_prompt = f"{system_prompt}\n\n{guardrails}"

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )
        
        if hasattr(response.content[0], 'text'):
            raw_content = response.content[0].text
        else:
            raw_content = response.content

        if raw_content is None:
            content = ""
        elif isinstance(raw_content, str):
            content = raw_content.strip()
        else:
            content = str(raw_content).strip()
        
        # 1. Try cleaning markdown code blocks
        clean_content = content
        if "```json" in clean_content:
            clean_content = clean_content.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_content:
            clean_content = clean_content.split("```")[1].split("```")[0].strip()
            
        try:
            # 2. Try direct JSON parse
            result = json.loads(clean_content)
            answer = result.get("answer") or ""
            if not answer.strip():
                salvaged = self._salvage_fields(content)
                salvaged_answer = ""
                if salvaged:
                    salvaged_answer = salvaged.get("answer") or ""
                if salvaged_answer.strip():
                    answer = salvaged_answer
                else:
                    answer = self._fallback_answer(state, content)

            return {
                "answer": answer,
                "citations": result.get("citations", []),
                "confidence_score": result.get("confidence_score", 0.0),
                "confidence_justification": result.get("confidence_justification", "")
            }
        except json.JSONDecodeError:
            # 3. Fallback: Try identifying the JSON object with regex or simple finding
            try:
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    possible_json = json_match.group(0)
                    result = json.loads(possible_json)
                    return {
                        "answer": result.get("answer", "Could not generate answer."),
                        "citations": result.get("citations", []),
                        "confidence_score": result.get("confidence_score", 0.0),
                        "confidence_justification": result.get("confidence_justification", "")
                    }
            except Exception:
                pass
                
            # 4. Resilient parsing: attempt to salvage fields from malformed JSON
            salvaged = self._salvage_fields(content)
            if salvaged:
                return salvaged

            # 5. Ultimate Fallback: Return raw content as the answer
            # This ensures the user gets *something* even if formatting failed
            print("JSON Parse failed. Returning raw content.")
            return {
                "answer": self._fallback_answer(state, content),
                "citations": [],
                "confidence_score": 0.0,
                "confidence_justification": "JSON parsing failed, returning raw output."
            }
        except Exception as e:
            print(f"Error generating final answer: {e}")
            return {
                "answer": self._fallback_answer(state, f"Error generating answer: {str(e)}"),
                "citations": [],
                "confidence_score": 0.0,
                "confidence_justification": f"Error: {e}"
            }

    @staticmethod
    def _scan_json_string(raw: str, start: int) -> str:
        buf = []
        escaped = False
        for idx in range(start, len(raw)):
            char = raw[idx]
            if escaped:
                buf.append(char)
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                return "".join(buf)
            buf.append(char)
        return "".join(buf)

    @classmethod
    def _extract_json_string(cls, raw: str, key: str) -> str | None:
        token = f'"{key}"'
        key_index = raw.find(token)
        if key_index == -1:
            return None
        colon_index = raw.find(":", key_index + len(token))
        if colon_index == -1:
            return None
        quote_index = raw.find('"', colon_index + 1)
        if quote_index == -1:
            return None
        return cls._scan_json_string(raw, quote_index + 1)

    @staticmethod
    def _extract_json_number(raw: str, key: str) -> float | None:
        match = re.search(rf'"{re.escape(key)}"\s*:\s*([0-9]+(?:\.[0-9]+)?)', raw)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    @staticmethod
    def _extract_json_list(raw: str, key: str):
        token = f'"{key}"'
        key_index = raw.find(token)
        if key_index == -1:
            return None
        start = raw.find("[", key_index)
        if start == -1:
            return None
        depth = 0
        for idx in range(start, len(raw)):
            char = raw[idx]
            if char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    candidate = raw[start:idx + 1]
                    try:
                        return json.loads(candidate)
                    except Exception:
                        return None
        return None

    @staticmethod
    def _extract_citations_from_text(raw: str) -> List[str]:
        citations = []
        seen = set()
        for match in re.findall(r"\[\[[^\]]+\]\]", raw):
            if match not in seen:
                citations.append(match)
                seen.add(match)
        for match in re.findall(r"https?://[^\s)>\"]+", raw):
            if match not in seen:
                citations.append(match)
                seen.add(match)
        return citations

    def _salvage_fields(self, raw: str) -> dict | None:
        answer = self._extract_json_string(raw, "answer")
        citations = self._extract_json_list(raw, "citations")
        confidence_score = self._extract_json_number(raw, "confidence_score")
        confidence_justification = self._extract_json_string(raw, "confidence_justification")

        if citations is None:
            citations = []
        if not citations:
            citations = self._extract_citations_from_text(raw)

        answer_value = answer
        if answer_value is None:
            answer_value = ""
        if isinstance(answer_value, str) and not answer_value.strip():
            answer_value = ""

        if answer_value or citations or confidence_score is not None or confidence_justification:
            return {
                "answer": answer_value,
                "citations": citations,
                "confidence_score": confidence_score or 0.0,
                "confidence_justification": confidence_justification or ""
            }
        return None

    @staticmethod
    def _fallback_answer(state: RAGState, raw: str) -> str:
        context = (state.get("accumulated_context") or "").strip()
        if context:
            note = ""
            raw_text = str(raw or "").strip()
            if raw_text:
                for marker in (
                    "Error generating answer",
                    "API Error",
                    "No choices returned",
                    "Empty response from OpenAI",
                    "Unsupported provider",
                    "No candidates returned",
                ):
                    if marker in raw_text:
                        snippet = raw_text[:240]
                        note = f" ({snippet})"
                        break
            return "No response from model" + note + ". Using retrieved context summary:\n\n" + context
        if raw:
            return raw
        return "No response from model. Please retry."
