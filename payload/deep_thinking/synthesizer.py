import json
import logging
import os
import re
from typing import Any, Dict, List, Tuple
from .state import RAGState
from .source_utils import canonicalize_web_url, normalize_vault_path
from .supervisor import RetrievalSupervisor
from .utils.universal_client import extract_response_text
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

logger = logging.getLogger(__name__)

try:
    from src.services.cascading_pipeline import source_set_covers_query_facets
except ImportError:
    def source_set_covers_query_facets(query: str, sources: List[Dict[str, Any]]) -> bool:
        return False

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
        if provider in ("lmstudio", "mlx"):
            return (
                int(os.getenv("DEEP_THINKING_LMSTUDIO_DOC_CHARS", os.getenv("DEEP_THINKING_MLX_DOC_CHARS", "4000"))),
                int(os.getenv("DEEP_THINKING_LMSTUDIO_TOTAL_CONTEXT_CHARS", os.getenv("DEEP_THINKING_MLX_TOTAL_CONTEXT_CHARS", "18000"))),
                int(os.getenv("DEEP_THINKING_LMSTUDIO_MAX_DOCS", os.getenv("DEEP_THINKING_MLX_MAX_DOCS", "6"))),
                int(os.getenv("DEEP_THINKING_LMSTUDIO_SUMMARY_CHARS", os.getenv("DEEP_THINKING_MLX_SUMMARY_CHARS", "4000"))),
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

    @staticmethod
    def _use_lazy_expansion_v2() -> bool:
        return os.getenv("DEEP_THINKING_LAZY_EXPANSION_V2", "false").strip().lower() in {
            "1", "true", "yes", "on"
        }

    @staticmethod
    def _is_web_doc(doc: Dict[str, Any]) -> bool:
        if doc.get("type") == "web" or doc.get("source_category") == "web":
            return True
        source = str(doc.get("source", "") or doc.get("filepath", ""))
        return source.startswith("http://") or source.startswith("https://")

    @staticmethod
    def _is_reasoning_doc(doc: Dict[str, Any]) -> bool:
        return not RetrievalSupervisor._is_graph_summary_doc(doc)

    @staticmethod
    def _is_citable_doc(doc: Dict[str, Any]) -> bool:
        return RetrievalSupervisor._is_citable_doc(doc)

    @classmethod
    def _citation_lookup(cls, documents: List[Dict[str, Any]]) -> tuple[Dict[str, str], Dict[str, str | None], Dict[str, str]]:
        vault_by_path: Dict[str, str] = {}
        vault_by_basename: Dict[str, str | None] = {}
        web_by_url: Dict[str, str] = {}

        for doc in documents or []:
            if not isinstance(doc, dict) or not cls._is_citable_doc(doc):
                continue

            source = str(doc.get("filepath") or doc.get("url") or doc.get("source") or "").strip()
            if not source:
                continue

            if cls._is_web_doc(doc):
                canonical_url = canonicalize_web_url(doc.get("canonical_url") or source) or source
                web_by_url[canonical_url.lower()] = canonical_url
                continue

            normalized_path = normalize_vault_path(source)
            if not normalized_path:
                continue
            vault_by_path[normalized_path.lower()] = normalized_path

            basename = os.path.basename(normalized_path).lower()
            existing = vault_by_basename.get(basename)
            if existing is None and basename not in vault_by_basename:
                vault_by_basename[basename] = normalized_path
            elif existing != normalized_path:
                vault_by_basename[basename] = None

        return vault_by_path, vault_by_basename, web_by_url

    @classmethod
    def _vault_alias_lookup(cls, documents: List[Dict[str, Any]]) -> Dict[str, str | None]:
        alias_map: Dict[str, str | None] = {}

        def register(alias: Any, path: str) -> None:
            text = normalize_vault_path(alias).strip()
            if not text:
                text = str(alias or "").strip()
            if not text:
                return
            text = text.strip()
            lowered = text.lower()
            existing = alias_map.get(lowered)
            if existing is None and lowered in alias_map:
                return
            if existing and existing != path:
                alias_map[lowered] = None
                return
            alias_map[lowered] = path

        for doc in documents or []:
            if not isinstance(doc, dict) or cls._is_web_doc(doc) or not cls._is_citable_doc(doc):
                continue
            path = normalize_vault_path(doc.get("filepath") or doc.get("source") or "")
            if not path:
                continue
            register(path, path)
            basename = os.path.basename(path)
            register(basename, path)
            if "." in basename:
                register(os.path.splitext(basename)[0], path)
            register(doc.get("filename"), path)
            filename = str(doc.get("filename") or "").strip()
            if filename and "." in filename:
                register(os.path.splitext(filename)[0], path)
            register(doc.get("title"), path)
            register(doc.get("canonical_id"), path)
            title = str(doc.get("title") or "").strip()
            if title:
                register(title.replace(" - ", "/"), path)
                register(title.replace(":", "/"), path)
        return alias_map

    @classmethod
    def _authoritative_documents(
        cls,
        question: str,
        retrieved_documents: List[Dict[str, Any]],
        max_docs: int,
    ) -> tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
        query_profile = RetrievalSupervisor.build_query_profile(question)
        reasoning_docs = [
            doc for doc in (retrieved_documents or [])
            if cls._is_reasoning_doc(doc)
        ]
        citable_reasoning_docs = [
            doc for doc in reasoning_docs
            if cls._is_citable_doc(doc)
        ]
        selected_doc_limit = query_profile["max_sources"] or max_docs
        selected_documents = RetrievalSupervisor.select_minimal_evidence_set(
            question,
            citable_reasoning_docs,
            max_docs=selected_doc_limit,
        )
        authoritative_documents = selected_documents or citable_reasoning_docs
        return query_profile, authoritative_documents, reasoning_docs

    @staticmethod
    def _retry_documents(documents: List[Dict[str, Any]], query_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not documents:
            return []
        if len(documents) == 1:
            return documents
        retry_limit = 2 if query_profile.get("is_summary_request") else 3
        reduced_count = min(len(documents) - 1, retry_limit)
        return documents[: max(1, reduced_count)]

    @staticmethod
    def _record_synthesis_failure(state: RAGState, reason: str, raw: str = "") -> None:
        state["_synthesis_failure_reason"] = reason
        snippet = str(raw or "").strip()[:240]
        logger.warning("Synthesis fallback reason=%s raw=%s", reason, snippet)
        warnings = state.setdefault("warnings", [])
        warning_msg = f"Synthesis fallback triggered: {reason}"
        if warning_msg not in warnings:
            warnings.append(warning_msg)

    @classmethod
    def _normalize_citations(
        cls,
        citations: List[Any],
        documents: List[Dict[str, Any]],
        query_entities: List[str] | None = None,
    ) -> List[str]:
        vault_by_path, vault_by_basename, web_by_url = cls._citation_lookup(documents)
        vault_aliases = cls._vault_alias_lookup(documents)
        normalized: List[str] = []
        seen: set[str] = set()
        dropped: List[str] = []

        for citation in citations or []:
            if not isinstance(citation, str):
                continue
            text = citation.strip()
            if not text:
                continue

            resolved: str | None = None
            obsidian_match = re.search(r"\[\[([^\]]+)\]\]", text)
            markdown_match = re.search(r"\[[^\]]+\]\(([^)]+)\)", text)

            if obsidian_match:
                candidate = normalize_vault_path(obsidian_match.group(1))
                direct = vault_by_path.get(candidate.lower())
                if direct:
                    resolved = f"[[{direct}]]"
                else:
                    basename = os.path.basename(candidate).lower()
                    matched = vault_by_basename.get(basename)
                    if not matched:
                        matched = vault_aliases.get(candidate.lower())
                    if matched and cls._document_path_matches_query_entities(matched, documents, query_entities):
                        resolved = f"[[{matched}]]"
            elif markdown_match:
                target = markdown_match.group(1).strip()
                if target.startswith("http://") or target.startswith("https://"):
                    canonical_url = canonicalize_web_url(target).lower()
                    resolved = web_by_url.get(canonical_url)
                else:
                    candidate = normalize_vault_path(target)
                    direct = vault_by_path.get(candidate.lower())
                    if direct:
                        resolved = f"[[{direct}]]"
            elif text.startswith("http://") or text.startswith("https://"):
                canonical_url = canonicalize_web_url(text).lower()
                resolved = web_by_url.get(canonical_url)
            else:
                candidate = normalize_vault_path(text)
                direct = vault_by_path.get(candidate.lower())
                if direct:
                    resolved = f"[[{direct}]]"
                else:
                    basename = os.path.basename(candidate).lower()
                    matched = vault_by_basename.get(basename)
                    if not matched:
                        matched = vault_aliases.get(candidate.lower())
                    if matched and cls._document_path_matches_query_entities(matched, documents, query_entities):
                        resolved = f"[[{matched}]]"

            if resolved and resolved not in seen:
                normalized.append(resolved)
                seen.add(resolved)
            elif not resolved:
                dropped.append(text)

        if dropped:
            print(f"Dropped invalid citations: {dropped}")

        return normalized

    @staticmethod
    def _relationship_max_chars() -> int:
        try:
            return max(120, int(os.getenv("DEEP_THINKING_RELATIONSHIP_MAX_CHARS", "350")))
        except (TypeError, ValueError):
            return 350

    @staticmethod
    def _allow_web_only_relationship_answers() -> bool:
        return os.getenv("DEEP_THINKING_ALLOW_WEB_ONLY_RELATIONSHIP_ANSWERS", "true").strip().lower() in {
            "1", "true", "yes", "on"
        }

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
    def _dedupe_documents(cls, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for doc in documents or []:
            key = cls._document_lookup_key(doc)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(doc)
        return deduped

    @classmethod
    def _ensure_vault_evidence_retained(
        cls,
        question: str,
        query_profile: Dict[str, Any],
        used_documents: List[Dict[str, Any]],
        selected_documents: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not cls._prefers_vault_first(question):
            return used_documents
        if any(not cls._is_web_doc(doc) for doc in (used_documents or [])):
            return used_documents

        vault_docs = [doc for doc in (selected_documents or []) if not cls._is_web_doc(doc)]
        if not vault_docs:
            return used_documents

        supplemental = RetrievalSupervisor.select_minimal_evidence_set(
            question,
            vault_docs,
            max_docs=query_profile.get("max_sources") or 3,
        ) or vault_docs[: max(1, min(len(vault_docs), query_profile.get("max_sources") or 3))]
        return cls._dedupe_documents(list(used_documents or []) + list(supplemental))

    @classmethod
    def _ensure_query_facet_coverage_retained(
        cls,
        question: str,
        used_documents: List[Dict[str, Any]],
        selected_documents: List[Dict[str, Any]],
        max_docs: int | None = None,
    ) -> List[Dict[str, Any]]:
        if not question or not selected_documents:
            return used_documents
        if source_set_covers_query_facets(question, used_documents or []):
            return used_documents
        if not source_set_covers_query_facets(question, selected_documents or []):
            return used_documents

        supplemented = RetrievalSupervisor.select_minimal_evidence_set(
            question,
            selected_documents,
            max_docs=max_docs or len(selected_documents),
        )
        combined = cls._dedupe_documents(list(used_documents or []) + list(supplemented or []))
        if source_set_covers_query_facets(question, combined):
            return combined
        return used_documents

    @classmethod
    def _document_path_matches_query_entities(
        cls,
        normalized_path: str,
        documents: List[Dict[str, Any]],
        query_entities: List[str] | None,
    ) -> bool:
        if not query_entities:
            return True
        normalized = normalize_vault_path(normalized_path).lower()
        for doc in documents or []:
            if normalize_vault_path(doc.get("filepath") or doc.get("source") or "").lower() != normalized:
                continue
            if any(RetrievalSupervisor._doc_contains_anchor(doc, entity) for entity in query_entities):
                return True
        return False

    @staticmethod
    def _document_lookup_key(doc: Dict[str, Any]) -> tuple[str, str]:
        source = str(doc.get("filepath") or doc.get("url") or doc.get("source") or doc.get("filename") or "").strip()
        category = str(doc.get("source_category") or "").strip().lower()
        if category != "web" and not source.startswith("http://") and not source.startswith("https://"):
            return "vault", normalize_vault_path(source).lower()
        canonical = canonicalize_web_url(doc.get("canonical_url") or source) or source
        return "web", canonical.lower()

    @classmethod
    def _resolve_used_documents(
        cls,
        citations: List[str],
        selected_documents: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not selected_documents:
            return []

        citation_targets = set()
        vault_by_path, vault_by_basename, web_by_url = cls._citation_lookup(selected_documents)
        for citation in citations or []:
            if not isinstance(citation, str):
                continue
            text = citation.strip()
            if not text:
                continue

            obsidian_match = re.search(r"\[\[([^\]]+)\]\]", text)
            markdown_match = re.search(r"\[[^\]]+\]\(([^)]+)\)", text)
            resolved: tuple[str, str] | None = None

            if obsidian_match:
                candidate = normalize_vault_path(obsidian_match.group(1))
                direct = vault_by_path.get(candidate.lower())
                if direct:
                    resolved = ("vault", direct.lower())
                else:
                    basename = os.path.basename(candidate).lower()
                    matched = vault_by_basename.get(basename)
                    if matched:
                        resolved = ("vault", matched.lower())
            elif markdown_match:
                target = markdown_match.group(1).strip()
                if target.startswith("http://") or target.startswith("https://"):
                    canonical = canonicalize_web_url(target).lower()
                    if canonical in web_by_url:
                        resolved = ("web", canonical)
                else:
                    candidate = normalize_vault_path(target)
                    direct = vault_by_path.get(candidate.lower())
                    if direct:
                        resolved = ("vault", direct.lower())
            elif text.startswith("http://") or text.startswith("https://"):
                canonical = canonicalize_web_url(text).lower()
                if canonical in web_by_url:
                    resolved = ("web", canonical)
            else:
                candidate = normalize_vault_path(text)
                direct = vault_by_path.get(candidate.lower())
                if direct:
                    resolved = ("vault", direct.lower())

            if resolved:
                citation_targets.add(resolved)

        if not citation_targets:
            return selected_documents

        used = [
            doc for doc in selected_documents
            if cls._document_lookup_key(doc) in citation_targets
        ]
        return used or selected_documents

    @staticmethod
    def _has_section_headers(text: str) -> bool:
        return bool(re.search(r"^\s*#{1,6}\s", str(text or ""), flags=re.MULTILINE))

    @staticmethod
    def _unique_citations(values: List[str]) -> List[str]:
        unique: List[str] = []
        seen: set[str] = set()
        for value in values or []:
            if not isinstance(value, str):
                continue
            text = value.strip()
            if not text or text in seen:
                continue
            seen.add(text)
            unique.append(text)
        return unique

    @classmethod
    def _relationship_claim_supported(cls, query_profile: Dict[str, Any], documents: List[Dict[str, Any]]) -> bool:
        query_text = str(query_profile.get("query") or "").strip()
        if query_text and source_set_covers_query_facets(query_text, documents):
            return True
        anchors = query_profile.get("anchor_entities", [])
        if not anchors:
            return bool(documents)
        if any(RetrievalSupervisor._doc_contains_all_anchors(doc, anchors) for doc in documents):
            return True
        if len(anchors) < 2:
            return any(RetrievalSupervisor._doc_contains_anchor(doc, anchors[0]) for doc in documents)

        left_docs = [doc for doc in documents if RetrievalSupervisor._doc_contains_anchor(doc, anchors[0])]
        right_docs = [doc for doc in documents if RetrievalSupervisor._doc_contains_anchor(doc, anchors[1])]
        if not left_docs or not right_docs:
            return False

        for left in left_docs:
            for right in right_docs:
                if left is right:
                    continue
                if RetrievalSupervisor._bridge_overlap_score(left, right, query_profile) >= 2:
                    return True
        return False

    @classmethod
    def _build_relationship_fallback_answer(
        cls,
        query_profile: Dict[str, Any],
        documents: List[Dict[str, Any]],
    ) -> str:
        anchors = query_profile.get("anchor_entities", [])
        if len(anchors) >= 2:
            if cls._relationship_claim_supported(query_profile, documents):
                return f"{anchors[0]} is related to {anchors[1]} based on the retrieved evidence, but the model output could not be validated cleanly. Review the attached sources for the exact relationship."
            return f"I found evidence about {anchors[0]} and {anchors[1]}, but the retrieved sources do not show a clear direct connection."
        return "The retrieved sources do not support a clear relationship answer."

    @classmethod
    def _enforce_relationship_length(cls, answer: str) -> str:
        text = re.sub(r"\s+", " ", str(answer or "").strip())
        if not text:
            return text
        sentences = re.split(r"(?<=[.!?])\s+", text)
        clipped = " ".join(sentences[:2]).strip()
        limit = cls._relationship_max_chars()
        if len(clipped) <= limit:
            return clipped
        return clipped[: limit - 3].rstrip() + "..."

    @classmethod
    def validate_answer_evidence_consistency(
        cls,
        answer: str,
        citations: List[str],
        used_documents: List[Dict[str, Any]],
        query_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_citations = cls._normalize_citations(
            citations,
            used_documents,
            query_profile.get("anchor_entities"),
        )
        inline_citations = cls._extract_citations_from_text(answer)
        normalized_inline = cls._normalize_citations(
            inline_citations,
            used_documents,
            query_profile.get("anchor_entities"),
        )
        merged = cls._unique_citations(normalized_citations + normalized_inline)
        valid = True
        reason = ""

        if len(normalized_citations) < len([c for c in citations or [] if isinstance(c, str) and c.strip()]):
            valid = False
            reason = "invalid_citation"
        elif inline_citations and len(normalized_inline) < len(inline_citations):
            valid = False
            reason = "inline_citation_mismatch"

        if query_profile.get("is_relationship"):
            if cls._has_section_headers(answer):
                valid = False
                reason = reason or "relationship_format"
            elif len(re.sub(r"\s+", " ", str(answer or "").strip())) > cls._relationship_max_chars():
                valid = False
                reason = reason or "relationship_too_long"
            elif not cls._relationship_claim_supported(query_profile, used_documents):
                valid = False
                reason = reason or "unsupported_relationship"

        return {
            "valid": valid,
            "reason": reason,
            "citations": merged,
            "used_documents": used_documents,
        }

    def _call_model_for_json(self, system_prompt: str, prompt: str, max_tokens: int):
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return extract_response_text(response)

    def _build_prompt_documents(
        self,
        documents: List[Dict[str, Any]],
        state: RAGState,
        provider: str,
        per_doc_char_limit: int,
        total_context_char_limit: int,
        max_docs: int,
        lazy_expansion_v2: bool,
        lazy_max_expanded_docs: int,
        lazy_max_expanded_bytes: int,
    ) -> tuple[str, str, List[str]]:
        vault_docs = ""
        web_docs = ""
        image_urls: List[str] = []
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

        prompt_docs = list(documents or [])
        if lazy_expansion_v2 and prompt_docs:
            expandable_docs = []
            seen_expandable = set()
            for doc in prompt_docs:
                images = doc.get("images")
                if images and isinstance(images, list):
                    for img in images:
                        if isinstance(img, str) and img.startswith("http"):
                            image_urls.append(img)
                        elif isinstance(img, dict) and img.get("url"):
                            image_urls.append(img["url"])

                if self._is_web_doc(doc):
                    continue
                source = doc.get("filepath") or doc.get("source")
                if not source or source in seen_expandable:
                    continue
                seen_expandable.add(source)
                expandable_docs.append(doc)
                if len(expandable_docs) >= lazy_max_expanded_docs:
                    break

            RetrievalSupervisor.expand_for_synthesis(
                expandable_docs,
                state,
                provider,
                max_docs=lazy_max_expanded_docs,
                max_total_bytes=lazy_max_expanded_bytes,
            )

        for doc in prompt_docs:
            images = doc.get("images")
            if images and isinstance(images, list):
                for img in images:
                    if isinstance(img, str) and img.startswith("http"):
                        image_urls.append(img)
                    elif isinstance(img, dict) and img.get("url"):
                        image_urls.append(img["url"])
            source = doc.get("source", "Unknown")
            append_doc(source, doc.get("content", ""), self._is_web_doc(doc))
            if consumed_docs >= max_docs or consumed_chars >= total_context_char_limit:
                break

        return vault_docs, web_docs, image_urls[:5]

    def _generate_relationship_attempt(
        self,
        state: RAGState,
        query_profile: Dict[str, Any],
        documents: List[Dict[str, Any]],
        provider: str,
        strict: bool,
    ) -> Dict[str, Any]:
        per_doc_char_limit, total_context_char_limit, max_docs, summary_char_limit = self._provider_limits(provider)
        lazy_expansion_v2 = self._use_lazy_expansion_v2()
        lazy_max_expanded_docs = int(os.getenv("DEEP_THINKING_LAZY_MAX_EXPANDED_DOCS", "8"))
        lazy_max_expanded_bytes = int(os.getenv("DEEP_THINKING_LAZY_MAX_EXPANDED_BYTES", "200000"))
        question = str(state.get("original_question", ""))
        research_summary = self._truncate_text(
            state.get("accumulated_context", ""),
            min(summary_char_limit, int(os.getenv("DEEP_THINKING_RELATIONSHIP_SUMMARY_CHARS", "1200"))),
        )
        vault_docs, web_docs, image_urls = self._build_prompt_documents(
            documents,
            state,
            provider,
            per_doc_char_limit,
            total_context_char_limit,
            min(max_docs, query_profile.get("max_sources") or max_docs),
            lazy_expansion_v2,
            lazy_max_expanded_docs,
            lazy_max_expanded_bytes,
        )
        images_section = ""
        if image_urls:
            images_section = "\nRelevant Images Found:\n" + "\n".join(
                f"- Image {idx + 1}: {url}" for idx, url in enumerate(image_urls[:5])
            )

        strict_clause = ""
        if strict:
            strict_clause = (
                f"\nAnswer in at most 2 short sentences and no more than {self._relationship_max_chars()} characters. "
                "Focus only on explaining the relationship between the two entities."
            )

        prompt = f"""
Original question: "{question}"

Research summary:
{research_summary}

Vault Documents:
{vault_docs}

Web Search Results:
{web_docs}
{images_section}

This is a relationship/connection question.
- Answer in 1-2 short sentences.
- State the relationship directly.
- Optional second sentence may explain mechanism, eligibility, or the nature of the link.
- No section headers.
- No trial names unless the question explicitly asks for outcomes.
- No long label text or broad overview.
- Keep citations to the minimal evidence actually used.{strict_clause}

Return ONLY a JSON object:
{{
  "answer": "...",
  "citations": ["[[Exact Document Name]]"],
  "confidence_score": 0.9,
  "confidence_justification": "Reasoning based closely on provided documents."
}}
""".strip()

        system_prompt = self.system_prompt
        guardrails = build_provider_guardrails(provider)
        if guardrails:
            system_prompt = f"{system_prompt}\n\n{guardrails}"

        max_tokens = int(os.getenv("DEEP_THINKING_MAX_TOKENS", "4096"))
        if provider == "claude":
            max_tokens = int(os.getenv("DEEP_THINKING_CLAUDE_MAX_TOKENS", "8192"))
        if provider in ("chatgpt", "openai"):
            max_tokens = int(os.getenv("DEEP_THINKING_OPENAI_MAX_TOKENS", str(max_tokens)))
        if provider in ("lmstudio", "mlx"):
            max_tokens = int(os.getenv("DEEP_THINKING_LMSTUDIO_MAX_TOKENS", os.getenv("DEEP_THINKING_MLX_MAX_TOKENS", "1024")))

        content = self._call_model_for_json(system_prompt, prompt, max_tokens)
        clean_content = content
        if "```json" in clean_content:
            clean_content = clean_content.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_content:
            clean_content = clean_content.split("```")[1].split("```")[0].strip()

        try:
            result = json.loads(clean_content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                result = json.loads(match.group(0))
            else:
                salvaged = self._salvage_fields(content) or {}
                result = salvaged

        answer = self._sanitize_answer(result.get("answer") or "", bool(web_docs.strip()))
        citations = self._normalize_citations(
            result.get("citations", []),
            documents,
            query_profile.get("anchor_entities"),
        )
        used_documents = self._resolve_used_documents(citations, documents)

        return {
            "answer": answer,
            "citations": citations,
            "confidence_score": result.get("confidence_score", 0.0),
            "confidence_justification": result.get("confidence_justification", ""),
            "used_documents": used_documents,
        }

    def generate(self, state: RAGState) -> dict:
        """
        Synthesize final answer with Obsidian-style citations.
        """
        provider = getattr(self.client, "provider", "").lower()
        per_doc_char_limit, total_context_char_limit, max_docs, summary_char_limit = self._provider_limits(provider)
        lazy_expansion_v2 = self._use_lazy_expansion_v2()
        lazy_max_expanded_docs = int(os.getenv("DEEP_THINKING_LAZY_MAX_EXPANDED_DOCS", "8"))
        lazy_max_expanded_bytes = int(os.getenv("DEEP_THINKING_LAZY_MAX_EXPANDED_BYTES", "200000"))
        question = str(state.get("original_question", ""))
        query_lower = question.lower()
        is_comparison_query = any(token in query_lower for token in [" vs ", " versus ", "compare", "difference"])
        query_profile, authoritative_documents, reasoning_docs = self._authoritative_documents(
            question,
            state.get("retrieved_documents", []),
            max_docs,
        )
        retry_documents = state.get("_synthesis_retry_documents")
        if isinstance(retry_documents, list):
            authoritative_documents = [doc for doc in retry_documents if isinstance(doc, dict)]
        if authoritative_documents:
            state["_selected_evidence_documents"] = authoritative_documents
        relationship_mode = bool(query_profile["is_relationship"])
        summary_mode = bool(query_profile.get("is_summary_request"))
        broad_summary_mode = summary_mode and state.get("summary_intent") == "broad"
        prefers_vault_first = self._prefers_vault_first(question)
        all_citable_reasoning_docs = [
            doc for doc in (reasoning_docs or [])
            if self._is_citable_doc(doc)
        ]

        if prefers_vault_first:
            authoritative_documents = self._ensure_vault_evidence_retained(
                question,
                query_profile,
                authoritative_documents,
                all_citable_reasoning_docs,
            )
            if authoritative_documents:
                state["_selected_evidence_documents"] = authoritative_documents

        if broad_summary_mode:
            broader_limit = max(
                query_profile.get("max_sources") or 0,
                min(max_docs, int(os.getenv("DEEP_THINKING_BROAD_SUMMARY_MAX_SOURCES", "4"))),
            )
            broader_candidates = [
                doc for doc in (reasoning_docs or [])
                if self._is_citable_doc(doc)
            ]
            broader_ranked = RetrievalSupervisor.rank_sources_for_query(
                question,
                broader_candidates,
                max_results=broader_limit,
            )
            if broader_ranked:
                authoritative_documents = broader_ranked[:broader_limit]
                state["_selected_evidence_documents"] = authoritative_documents

        if relationship_mode:
            attempt_queue: List[Dict[str, Any]] = [{
                "documents": authoritative_documents,
                "strict": False,
                "web_only": False,
            }]
            web_only_docs: List[Dict[str, Any]] = []
            if (
                query_profile.get("is_medical")
                and self._allow_web_only_relationship_answers()
                and not prefers_vault_first
            ):
                candidate_web_docs = [doc for doc in authoritative_documents if self._is_web_doc(doc)]
                if candidate_web_docs:
                    web_only_docs = RetrievalSupervisor.select_minimal_evidence_set(
                        question,
                        candidate_web_docs,
                        max_docs=query_profile.get("max_sources") or 3,
                    )

            attempted: set[tuple[tuple[tuple[str, str], ...], bool, bool]] = set()
            last_result: Dict[str, Any] | None = None
            last_reason = ""

            while attempt_queue:
                attempt = attempt_queue.pop(0)
                documents = attempt.get("documents") or []
                doc_signature = tuple(sorted(self._document_lookup_key(doc) for doc in documents))
                attempt_key = (doc_signature, bool(attempt.get("strict")), bool(attempt.get("web_only")))
                if attempt_key in attempted:
                    continue
                attempted.add(attempt_key)
                if not documents:
                    continue

                result = self._generate_relationship_attempt(
                    state,
                    query_profile,
                    documents,
                    provider,
                    strict=bool(attempt.get("strict")),
                )
                validation = self.validate_answer_evidence_consistency(
                    result.get("answer", ""),
                    result.get("citations", []),
                    result.get("used_documents", []) or documents,
                    query_profile,
                )
                last_result = result
                last_reason = validation.get("reason", "")

                if validation["valid"]:
                    result["citations"] = validation["citations"]
                    result["used_documents"] = self._ensure_vault_evidence_retained(
                        question,
                        query_profile,
                        validation["used_documents"],
                        documents,
                    )
                    result["used_documents"] = self._ensure_query_facet_coverage_retained(
                        question,
                        result["used_documents"],
                        documents,
                        max_docs=query_profile.get("max_sources") or len(documents),
                    )
                    result["answer"] = self._enforce_relationship_length(result.get("answer", ""))
                    return result

                if not attempt.get("strict"):
                    attempt_queue.insert(0, {
                        "documents": documents,
                        "strict": True,
                        "web_only": bool(attempt.get("web_only")),
                    })

                if (
                    query_profile.get("is_medical")
                    and self._allow_web_only_relationship_answers()
                    and web_only_docs
                    and not attempt.get("web_only")
                    and any(not self._is_web_doc(doc) for doc in documents)
                ):
                    attempt_queue.append({
                        "documents": web_only_docs,
                        "strict": True,
                        "web_only": True,
                    })

            fallback_docs = web_only_docs or authoritative_documents
            fallback_answer = self._build_relationship_fallback_answer(query_profile, fallback_docs)
            if last_result and last_result.get("answer") and self._relationship_claim_supported(query_profile, fallback_docs):
                fallback_answer = self._enforce_relationship_length(last_result.get("answer", ""))

            normalized_citations = self._normalize_citations(
                (last_result or {}).get("citations", []),
                fallback_docs,
                query_profile.get("anchor_entities"),
            )
            used_documents = self._ensure_vault_evidence_retained(
                question,
                query_profile,
                self._resolve_used_documents(normalized_citations, fallback_docs),
                fallback_docs,
            )
            used_documents = self._ensure_query_facet_coverage_retained(
                question,
                used_documents,
                fallback_docs,
                max_docs=query_profile.get("max_sources") or len(fallback_docs),
            )
            return {
                "answer": fallback_answer,
                "citations": normalized_citations,
                "confidence_score": (last_result or {}).get("confidence_score", 0.0),
                "confidence_justification": (last_result or {}).get("confidence_justification", "") or last_reason,
                "used_documents": used_documents,
            }

        vault_docs, web_docs, image_urls = self._build_prompt_documents(
            authoritative_documents,
            state,
            provider,
            per_doc_char_limit,
            total_context_char_limit,
            max_docs,
            lazy_expansion_v2,
            lazy_max_expanded_docs,
            lazy_max_expanded_bytes,
        )

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
        
        effective_summary_limit = summary_char_limit
        if relationship_mode:
            effective_summary_limit = min(summary_char_limit, int(os.getenv("DEEP_THINKING_RELATIONSHIP_SUMMARY_CHARS", "1200")))
        research_summary = self._truncate_text(state['accumulated_context'], effective_summary_limit)

        comparison_instruction = ""
        if is_comparison_query:
            comparison_instruction = """
        12. Because this is a comparison query, include:
            - a compact side-by-side table of key specs/capabilities
            - a "When to choose X" recommendation block with concrete tradeoffs
            - at least 5 substantive comparison points.
        """

        relationship_instruction = ""
        summary_instruction = ""
        prompt_task = "Generate a comprehensive answer that:"
        web_instruction = """
        5. You MUST include a separate "## Web Findings" section if any web search results are provided. Use this section to explain standard definitions, methodologies, or external context found in the web results.
        """
        if summary_mode:
            if broad_summary_mode:
                prompt_task = "Generate a broad point-form synthesis that:"
            else:
                prompt_task = "Generate a concise point-form summary that:"
            web_instruction = """
        5. If web search results are provided, use them only when the user explicitly asked for outside context or review material. Do NOT add a separate "Web Findings" section for a normal vault summary.
        """
            if broad_summary_mode:
                summary_instruction = """
        12. This is a deep-thinking summary request.
            - Answer as a broader point-form synthesis, not a narrow excerpt compression.
            - Cover the major themes, mechanisms, methods, and practical applications present across the retrieved vault evidence.
            - Prefer 5-8 bullets when the evidence supports it.
            - If the retrieved evidence only supports one cluster of ideas, say that the vault coverage is limited rather than inventing breadth.
            - Keep the citations array to the minimal vault note set actually used.
        """
            else:
                summary_instruction = """
        12. This is a summary request.
            - Answer as concise bullet points.
            - Focus on the main ideas, methods, and memorable takeaways from the retrieved note(s).
            - Do NOT add generic framing, introductions, or conclusions.
            - Keep the citations array to the minimal vault note set actually used.
        """
        if relationship_mode:
            web_instruction = """
        5. If web results are provided, use them only when they add a unique fact not already present in the vault evidence. Do NOT add a separate "Web Findings" section for a simple relationship question unless an external source is essential.
        """
            relationship_instruction = """
        12. This is a simple relationship/connection question.
            - Answer in 1-2 core sentences.
            - State the relationship directly and plainly.
            - Optionally add at most 2 short bullets only for line-of-therapy limits or major exclusions that materially change the connection.
            - Do NOT turn the answer into a long label summary.
            - Do NOT mention trials unless they are necessary; if you mention one, include the key outcome in a short clause.
            - Keep the citations array to the minimal evidence set actually needed.
        """

        prompt = f"""
        Original question: "{question}"
        
        Research summary:
        {research_summary}
        
        Vault Documents:
        {vault_docs}
        
        Web Search Results:
        {web_docs}
        {images_section}
        
        {prompt_task}
        1. Directly addresses the original question using a structured cognitive format.
        2. Synthesizes findings from all research steps. You MUST INTEGRATE information from the Vault Documents if any are provided.
        3. Cites vault sources using Obsidian link format ONLY: [[Folder/Note Name]]. Do NOT output Vault links as URLs.
        4. Cites web sources using markdown links with the ACTUAL page title from the web results: [Actual Page Title](https://example.com).
        {web_instruction}
        6. If images are provided above, embed relevant ones using markdown format: ![Description](image_url)
        7. Acknowledges any gaps or uncertainties
        8. DO NOT INVENT CITATIONS. Only use the Exact Names of Vault Documents or URLs provided above.
        9. CRITICAL: Never cite the section headers (e.g., do NOT output "[[Vault Documents]]"). Cite the specific name of the source provided in the list.
        10. If the Web Search Results section is empty, your "citations" array should ONLY contain Vault Document names.
        11. If the Web Search Results section is empty, you MUST NOT include a "Web Findings" section and you MUST NOT introduce external facts.
        12. STRUCTURAL REQUIREMENT: Unless superseded by comparison/summary/relationship instructions below, your answer MUST use the following cognitive structure:
            - **Problem Framing**: A brief statement of the core issue, context, or question being explored.
            - **Concept Graphing**: An interconnected breakdown of the underlying ideas, mechanisms, and how they relate to each other (synthesizing across the retrieved context).
            - **Applied Recipes**: Actionable synthesis detailing how the user can actually run these mental models, execute the steps, or apply the theory.
        {comparison_instruction}
        {summary_instruction}
        {relationship_instruction}

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
        if provider in ("lmstudio", "mlx"):
            max_tokens = int(os.getenv("DEEP_THINKING_LMSTUDIO_MAX_TOKENS", os.getenv("DEEP_THINKING_MLX_MAX_TOKENS", "1024")))

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
        content = extract_response_text(response)
        
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
            normalized_citations = self._normalize_citations(
                result.get("citations", []),
                authoritative_documents,
                query_profile.get("anchor_entities"),
            )
            used_documents = self._resolve_used_documents(normalized_citations, authoritative_documents)
            used_documents = self._ensure_query_facet_coverage_retained(
                question,
                used_documents,
                authoritative_documents,
                max_docs=query_profile.get("max_sources") or len(authoritative_documents),
            )
            if not answer.strip():
                salvaged = self._salvage_fields(content)
                salvaged_answer = ""
                if salvaged:
                    salvaged_answer = salvaged.get("answer") or ""
                if salvaged_answer.strip():
                    answer = self._sanitize_answer(salvaged_answer, has_web_docs)
                else:
                    if not state.get("_synthesis_retry_performed"):
                        reduced_documents = self._retry_documents(authoritative_documents, query_profile)
                        if reduced_documents and reduced_documents != authoritative_documents:
                            retry_state = dict(state)
                            retry_state["_synthesis_retry_performed"] = True
                            retry_state["_synthesis_retry_documents"] = reduced_documents
                            return self.generate(retry_state)
                    self._record_synthesis_failure(state, "empty_answer", content)
                    answer = self._sanitize_answer(self._fallback_answer(state, content), has_web_docs)

            return {
                "answer": answer,
                "citations": normalized_citations,
                "confidence_score": result.get("confidence_score", 0.0),
                "confidence_justification": result.get("confidence_justification", ""),
                "used_documents": used_documents,
            }
        except json.JSONDecodeError:
            # 3. Fallback: Try identifying the JSON object with regex or simple finding
            try:
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    possible_json = json_match.group(0)
                    result = json.loads(possible_json)
                    normalized_citations = self._normalize_citations(
                        result.get("citations", []),
                        authoritative_documents,
                        query_profile.get("anchor_entities"),
                    )
                    return {
                        "answer": self._sanitize_answer(result.get("answer", "Could not generate answer."), has_web_docs),
                        "citations": normalized_citations,
                        "confidence_score": result.get("confidence_score", 0.0),
                        "confidence_justification": result.get("confidence_justification", ""),
                        "used_documents": self._ensure_query_facet_coverage_retained(
                            question,
                            self._resolve_used_documents(normalized_citations, authoritative_documents),
                            authoritative_documents,
                            max_docs=query_profile.get("max_sources") or len(authoritative_documents),
                        ),
                    }
            except Exception:
                pass
                
            # 4. Resilient parsing: attempt to salvage fields from malformed JSON
            salvaged = self._salvage_fields(content)
            if salvaged:
                salvaged["answer"] = self._sanitize_answer(salvaged.get("answer", ""), has_web_docs)
                salvaged["citations"] = self._normalize_citations(
                    salvaged.get("citations", []),
                    authoritative_documents,
                    query_profile.get("anchor_entities"),
                )
                salvaged["used_documents"] = self._resolve_used_documents(salvaged.get("citations", []), authoritative_documents)
                if not str(salvaged.get("answer") or "").strip():
                    plain_text = self._salvage_plain_text_answer(content, has_web_docs)
                    if plain_text:
                        citations = self._normalize_citations(
                            plain_text.get("citations", []),
                            authoritative_documents,
                            query_profile.get("anchor_entities"),
                        )
                        return {
                            "answer": plain_text["answer"],
                            "citations": citations,
                            "confidence_score": plain_text["confidence_score"],
                            "confidence_justification": plain_text["confidence_justification"],
                            "used_documents": self._resolve_used_documents(citations, authoritative_documents),
                        }
                    if not state.get("_synthesis_retry_performed"):
                        reduced_documents = self._retry_documents(authoritative_documents, query_profile)
                        if reduced_documents and reduced_documents != authoritative_documents:
                            retry_state = dict(state)
                            retry_state["_synthesis_retry_performed"] = True
                            retry_state["_synthesis_retry_documents"] = reduced_documents
                            return self.generate(retry_state)
                    self._record_synthesis_failure(state, "empty_answer", content)
                    salvaged["answer"] = self._sanitize_answer(self._fallback_answer(state, content), has_web_docs)
                return salvaged

            plain_text = self._salvage_plain_text_answer(content, has_web_docs)
            if plain_text:
                citations = self._normalize_citations(
                    plain_text.get("citations", []),
                    authoritative_documents,
                    query_profile.get("anchor_entities"),
                )
                return {
                    "answer": plain_text["answer"],
                    "citations": citations,
                    "confidence_score": plain_text["confidence_score"],
                    "confidence_justification": plain_text["confidence_justification"],
                    "used_documents": self._resolve_used_documents(citations, authoritative_documents),
                }

            # 5. Ultimate Fallback: Return raw content as the answer
            # This ensures the user gets *something* even if formatting failed
            print("JSON Parse failed. Returning raw content.")
            self._record_synthesis_failure(state, "json_parse_failure", content)
            return {
                "answer": self._sanitize_answer(self._fallback_answer(state, content), has_web_docs),
                "citations": [],
                "confidence_score": 0.0,
                "confidence_justification": "JSON parsing failed, returning raw output.",
                "used_documents": authoritative_documents,
            }
        except Exception as e:
            print(f"Error generating final answer: {e}")
            failure_reason = "timeout" if "timeout" in str(e).lower() else "provider_exception"
            self._record_synthesis_failure(state, failure_reason, str(e))
            return {
                "answer": self._sanitize_answer(self._fallback_answer(state, f"Error generating answer: {str(e)}"), has_web_docs),
                "citations": [],
                "confidence_score": 0.0,
                "confidence_justification": f"Error: {e}",
                "used_documents": authoritative_documents,
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
    def _salvage_plain_text_answer(raw: str, has_web_docs: bool) -> dict | None:
        text = str(raw or "").strip()
        if not text:
            return None

        fence_match = re.fullmatch(r"```(?:\w+)?\s*(.*?)\s*```", text, flags=re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()

        lowered = text.lower()
        if any(
            marker in lowered
            for marker in (
                "error generating answer",
                "api error",
                "no choices returned",
                "empty response from openai",
                "unsupported provider",
                "no candidates returned",
                "model returned unusable json",
                "no response from model",
            )
        ):
            return None

        if text.lstrip().startswith(("{", "[")):
            return None

        if not re.search(r"[A-Za-z]", text):
            return None

        word_count = len(re.findall(r"\b\w+\b", text))
        looks_structured = bool(re.search(r"(?m)^\s*(?:[-*•]|\d+\.)\s+\S", text)) or bool(
            re.search(r"^\s*#{1,6}\s", text, flags=re.MULTILINE)
        )
        if word_count < 8 and not looks_structured:
            return None

        return {
            "answer": FinalAnswerGenerator._sanitize_answer(text, has_web_docs),
            "citations": FinalAnswerGenerator._extract_citations_from_text(text),
            "confidence_score": 0.0,
            "confidence_justification": "Model returned plain text instead of the required JSON format.",
        }

    @staticmethod
    def _fallback_answer(state: RAGState, raw: str) -> str:
        context = (state.get("accumulated_context") or "").strip()
        failure_reason = str(state.get("_synthesis_failure_reason") or "").strip().lower()
        reason_message = {
            "empty_answer": "Model returned an empty answer; showing retrieved context summary instead",
            "json_parse_failure": "Model returned unusable JSON; showing retrieved context summary instead",
            "timeout": "Model request timed out; showing retrieved context summary instead",
            "provider_exception": "Model call failed; showing retrieved context summary instead",
        }.get(failure_reason, "No response from model. Using retrieved context summary instead")
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
            return reason_message + note + ":\n\n" + context
        if raw:
            return raw
        if failure_reason:
            return reason_message + "."
        return "No response from model. Please retry."
