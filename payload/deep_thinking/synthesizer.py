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
1. Reference the user's specific context or timeline from their profile when relevant.
2. Incorporate insights from their **Obsidian notes**, citing which notes or sources you use.
3. Maintain an appropriate tone for the topic.
4. Provide **technical depth** and precision for engineering and coding topics.
5. Adapt to their **expert-level understanding** — avoid overexplaining known concepts.
6. Be **concise but thorough**, focusing on clarity and reasoning.
7. Avoid redundant or generic phrasing.

Finally, provide your answer in a structured, easy-to-read format."""

    @staticmethod
    def _provider_limits(provider: str) -> tuple[int, int, int, int]:
        provider = (provider or "").lower()
        if provider == "mlx":
            return (
                int(os.getenv("DEEP_THINKING_MLX_DOC_CHARS", "4000")),
                int(os.getenv("DEEP_THINKING_MLX_TOTAL_CONTEXT_CHARS", "18000")),
                int(os.getenv("DEEP_THINKING_MLX_MAX_DOCS", "6")),
                int(os.getenv("DEEP_THINKING_MLX_SUMMARY_CHARS", "4000")),
            )
        return (
            int(os.getenv("DEEP_THINKING_DOC_CHARS", "12000")),
            int(os.getenv("DEEP_THINKING_TOTAL_CONTEXT_CHARS", "60000")),
            int(os.getenv("DEEP_THINKING_MAX_DOCS", "10")),
            int(os.getenv("DEEP_THINKING_SUMMARY_CHARS", "12000")),
        )

    @staticmethod
    def _truncate_text(value: str, limit: int) -> str:
        text = str(value or "")
        if len(text) <= limit:
            return text
        return text[: max(limit - 32, 0)].rstrip() + "\n... [truncated]"

    def generate(self, state: RAGState) -> dict:
        """
        Synthesize final answer with Obsidian-style citations.
        """
        provider = getattr(self.client, "provider", "").lower()
        per_doc_char_limit, total_context_char_limit, max_docs, summary_char_limit = self._provider_limits(provider)
        query_lower = str(state.get("original_question", "")).lower()
        is_comparison_query = any(token in query_lower for token in [" vs ", " versus ", "compare", "difference"])

        # Format documents for citation
        vault_docs = ""
        web_docs = ""
        image_urls = []
        consumed_chars = 0
        consumed_docs = 0

        def append_doc(source: str, content: str, is_web: bool) -> None:
            nonlocal vault_docs, web_docs, consumed_chars, consumed_docs
            if consumed_docs >= max_docs or consumed_chars >= total_context_char_limit:
                return

            trimmed = self._truncate_text(content or "", per_doc_char_limit)
            remaining = total_context_char_limit - consumed_chars
            if remaining <= 0:
                return
            if len(trimmed) > remaining:
                trimmed = self._truncate_text(trimmed, remaining)

            block = f"[{consumed_docs + 1}] {source}\nContent: {trimmed}\n\n"
            if is_web:
                web_docs += block
            else:
                vault_docs += block
            consumed_chars += len(trimmed)
            consumed_docs += 1
        
        # Priority 1: Use Raw Context Buffer if available (high fidelity)
        raw_buffer = state.get("raw_context_buffer", [])
        if raw_buffer:
            for item in raw_buffer:
                source = item.get("source", "Unknown")
                append_doc(
                    source,
                    item.get("content", ""),
                    "http" in source and "localhost" not in source
                )
                if consumed_docs >= max_docs or consumed_chars >= total_context_char_limit:
                    break
                    
        # Priority 2: Fallback to standard retrieved_documents (if buffer empty)
        else:
            for doc in state['retrieved_documents']:
                source = doc.get('source', 'Unknown')
                
                # Collect images from web results safely
                images = doc.get('images')
                if images and isinstance(images, list):
                    for img in images:
                        if isinstance(img, str) and img.startswith('http'):
                            image_urls.append(img)
                        elif isinstance(img, dict) and img.get('url'):
                            image_urls.append(img['url'])
                
                append_doc(source, doc.get('content', ''), doc.get('type') == 'web')
                if consumed_docs >= max_docs or consumed_chars >= total_context_char_limit:
                    break

        # DEEP THINKING DEBUG
        print(f"DEBUG SYNTHESIZER: Vault Docs Length: {len(vault_docs)}")
        print(f"DEBUG SYNTHESIZER: Web Docs Length: {len(web_docs)}")
        print(f"DEBUG SYNTHESIZER: Number of Vault Docs listed: {vault_docs.count('Content:')}")
        print(f"DEBUG SYNTHESIZER: Number of Web Docs listed: {web_docs.count('Content:')}")
        has_web_docs = bool(web_docs.strip())

        # Build image section for prompt
        images_section = ""
        if image_urls:
            images_section = f"\n        Relevant Images Found:\n"
            for idx, img_url in enumerate(image_urls[:5]):  # Limit to top 5 images
                images_section += f"        - Image {idx+1}: {img_url}\n"
        
        research_summary = self._truncate_text(state['accumulated_context'], summary_char_limit)

        comparison_instruction = ""
        if is_comparison_query:
            comparison_instruction = """
        12. Because this is a comparison query, include:
            - a compact side-by-side table of key specs/capabilities
            - a "When to choose X" recommendation block with concrete tradeoffs
            - at least 5 substantive comparison points.
        """

        prompt = f"""
        Original question: "{state['original_question']}"
        
        Research summary:
        {research_summary}
        
        Vault Documents:
        {vault_docs}
        
        Web Search Results:
        {web_docs}
        {images_section}
        
        Generate a comprehensive answer that:
        1. Directly addresses the original question
        2. Synthesizes findings from all research steps. You MUST INTEGRATE information from the Vault Documents if any are provided. Do not ignore the user's personal vault notes.
        3. Cites vault sources using Obsidian link format ONLY: [[Folder/Note Name]]. Do NOT output Vault links as URLs (e.g. no "http://...md").
        4. Cites web sources using markdown links with the ACTUAL page title from the web results: [Actual Page Title](https://example.com).
        5. You MUST include a separate "## Web Findings" section if any web search results are provided. Use this section to explain standard definitions, methodologies, or external context found in the web results.
        6. If images are provided above, embed relevant ones using markdown format: ![Description](image_url)
           - For hardware/wiring questions, prioritize pinout diagrams and wiring schematics
           - Place images in appropriate sections (e.g., under "Hardware Connection" or "Wiring Diagram")
        7. Acknowledges any gaps or uncertainties
        8. DO NOT INVENT CITATIONS. Only use the Exact Names of Vault Documents or URLs provided above. If no Web Search Results are provided, you MUST NOT output any URLs.
        9. CRITICAL: Never cite the section headers (e.g., do NOT output "[[Vault Documents]]" or "Web Source"). Cite the specific name of the source provided in the list (e.g. "[[Tech/ESP32/note.md]]").
        10. If the Web Search Results section is empty, your "citations" array should ONLY contain Vault Document names. Do not hallucinate websites.
        11. If the Web Search Results section is empty, you MUST NOT include a "Web Findings" section and you MUST NOT introduce external facts, datasheet details, or website titles that are not explicitly present in the Vault Documents.
        {comparison_instruction}

        Return ONLY a JSON object:
        {{
            "answer": "...",
            "citations": ["[[Exact Document Name]]"],
            "confidence_score": 0.9,
            "confidence_justification": "Reasoning based closely on provided documents..."
        }}
        """

        prompt_appendix = build_prompt_appendix(state["original_question"], provider)
        if prompt_appendix:
            prompt = f"{prompt}\n\n{prompt_appendix}\n"

        max_tokens = int(os.getenv("DEEP_THINKING_MAX_TOKENS", "4096"))
        if provider == "claude":
            max_tokens = int(os.getenv("DEEP_THINKING_CLAUDE_MAX_TOKENS", "8192"))
        if provider in ("chatgpt", "openai"):
            max_tokens = int(os.getenv("DEEP_THINKING_OPENAI_MAX_TOKENS", str(max_tokens)))
        if provider == "mlx":
            max_tokens = int(os.getenv("DEEP_THINKING_MLX_MAX_TOKENS", "1024"))

        system_prompt = self.system_prompt
        guardrails = build_provider_guardrails(provider)
        if guardrails:
            system_prompt = f"{system_prompt}\n\n{guardrails}"

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
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
            answer = self._sanitize_answer(result.get("answer") or "", has_web_docs)
            if not answer.strip():
                salvaged = self._salvage_fields(content)
                salvaged_answer = ""
                if salvaged:
                    salvaged_answer = salvaged.get("answer") or ""
                if salvaged_answer.strip():
                    answer = self._sanitize_answer(salvaged_answer, has_web_docs)
                else:
                    answer = self._sanitize_answer(self._fallback_answer(state, content), has_web_docs)

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
                        "answer": self._sanitize_answer(result.get("answer", "Could not generate answer."), has_web_docs),
                        "citations": result.get("citations", []),
                        "confidence_score": result.get("confidence_score", 0.0),
                        "confidence_justification": result.get("confidence_justification", "")
                    }
            except Exception:
                pass
                
            # 4. Resilient parsing: attempt to salvage fields from malformed JSON
            salvaged = self._salvage_fields(content)
            if salvaged:
                salvaged["answer"] = self._sanitize_answer(salvaged.get("answer", ""), has_web_docs)
                return salvaged

            # 5. Ultimate Fallback: Return raw content as the answer
            # This ensures the user gets *something* even if formatting failed
            print("JSON Parse failed. Returning raw content.")
            return {
                "answer": self._sanitize_answer(self._fallback_answer(state, content), has_web_docs),
                "citations": [],
                "confidence_score": 0.0,
                "confidence_justification": "JSON parsing failed, returning raw output."
            }
        except Exception as e:
            print(f"Error generating final answer: {e}")
            return {
                "answer": self._sanitize_answer(self._fallback_answer(state, f"Error generating answer: {str(e)}"), has_web_docs),
                "citations": [],
                "confidence_score": 0.0,
                "confidence_justification": f"Error: {e}"
            }

    @staticmethod
    def _sanitize_answer(answer: str, has_web_docs: bool) -> str:
        text = str(answer or "")
        if has_web_docs or not text.strip():
            return text

        patterns = [
            r"\n## Web Findings\b.*?(?=\n## |\n# |\Z)",
            r"\n### Web Findings\b.*?(?=\n## |\n# |\n### |\Z)",
            r"\n\*\*Web Findings\*\*.*?(?=\n## |\n# |\n### |\Z)",
        ]
        cleaned = text
        for pattern in patterns:
            cleaned = re.sub(pattern, "\n", cleaned, flags=re.IGNORECASE | re.DOTALL)

        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        return cleaned

    @staticmethod
    def _scan_json_string(raw: str, start: int) -> str:
        buf = []
        escaped = False
        escape_map = {
            "n": "\n",
            "r": "\r",
            "t": "\t",
            '"': '"',
            "\\": "\\",
            "/": "/",
            "b": "\b",
            "f": "\f",
        }
        for idx in range(start, len(raw)):
            char = raw[idx]
            if escaped:
                buf.append(escape_map.get(char, char))
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
            # The AI might hallucinate a URL by prepending http:// to a Vault node. Filter out obvious fake URLs.
            if match.endswith(".md") or match.endswith(".html"):
                continue
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
