import logging
import os
from typing import List, Dict, Any, Optional
import asyncio
import httpx
import re

try:
    from cascading_pipeline import (
        distance_to_relevance,
        extract_query_facets,
        has_multi_facet_query,
        source_set_covers_query_facets,
    )
    from internal_graph_transport import query_networkx_graph, query_lightrag
except ImportError:
    from src.services.cascading_pipeline import (
        distance_to_relevance,
        extract_query_facets,
        has_multi_facet_query,
        source_set_covers_query_facets,
    )
    from src.services.internal_graph_transport import query_networkx_graph, query_lightrag

logger = logging.getLogger(__name__)


def _get_env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return float(default)


class CascadingRetriever:
    """
    Implements a 5-stage 'Waterfall' retrieval pipeline:
    1. Anchor: Find Notes matching the query.
    2. Extract: Pull technical entities/keywords from those notes.
    3. Expand: Use the Knowledge Graph (LightRAG) to find related concepts.
    4. Target: Use new keywords to run high-precision Vector Search.
    5. Synthesize: Package results for the LLM.
    """

    def __init__(
        self,
        embed_url: str = "http://localhost:8000",
        graph_url: str = "http://localhost:8002",
        lightrag_url: str = "http://localhost:8001",
        llm_provider: str = "claude",  # Default, can be overridden per query
        llm_model: str = "",
        api_key: Optional[str] = None,
    ):
        self.embed_url = embed_url
        self.graph_url = graph_url
        self.lightrag_url = lightrag_url
        self.llm_provider = llm_provider
        self.llm_model = str(llm_model or "").strip()
        self.api_key = api_key
        self.use_internal_graph_transport = (
            os.getenv("OBSIDIAN_RAG_INTERNAL_GRAPH_TRANSPORT", "true").strip().lower()
            in {"1", "true", "yes", "on"}
        )

        # We might need a lightweight LLM client for entity extraction if not using regex
        # For now, we'll rely on the services or simple extraction
        self.stopwords = {
            "and",
            "or",
            "the",
            "a",
            "an",
            "in",
            "on",
            "with",
            "for",
            "to",
            "of",
            "from",
            "by",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "it",
            "this",
            "that",
            "these",
            "those",
            "as",
            "at",
            "via",
            "etc",
            "notes",
            "note",
            "file",
            "files",
            "doc",
            "docs",
            "page",
            "pages",
            "summary",
        }

        # Remove overly aggressive stopword filtering for technical terms
        # Keep core English stopwords but allow technical terms like "ESPHome"
        self.vector_thresholds = [60, 40]

    def _graph_stage_timeout_seconds(self) -> float:
        provider = str(self.llm_provider or "").strip().lower()
        if provider == "ollama":
            return _get_env_float(
                "CASCADING_GRAPH_STAGE_TIMEOUT_SECONDS_OLLAMA",
                _get_env_float("OLLAMA_TIMEOUT", 240.0),
            )
        if provider == "lmstudio":
            return _get_env_float("CASCADING_GRAPH_STAGE_TIMEOUT_SECONDS_LMSTUDIO", 20.0)
        return _get_env_float("CASCADING_GRAPH_STAGE_TIMEOUT_SECONDS", 30.0)

    def _expansion_stage_timeout_seconds(self) -> float:
        provider = str(self.llm_provider or "").strip().lower()
        if provider == "ollama":
            return _get_env_float(
                "CASCADING_EXPANSION_STAGE_TIMEOUT_SECONDS_OLLAMA",
                _get_env_float("OLLAMA_TIMEOUT", 240.0),
            )
        if provider == "lmstudio":
            return _get_env_float("CASCADING_EXPANSION_STAGE_TIMEOUT_SECONDS_LMSTUDIO", 20.0)
        return _get_env_float("CASCADING_EXPANSION_STAGE_TIMEOUT_SECONDS", 60.0)

    def _service_headers(self) -> Dict[str, str]:
        api_key = os.getenv("OBSIDIAN_RAG_API_KEY")
        if not api_key:
            return {}
        return {"X-API-Key": api_key}

    def _extract_terms(self, text: str) -> set:
        tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", text.lower())
        return {t for t in tokens if t not in self.stopwords and not t.isdigit()}

    def _extract_named_phrases(self, text: str) -> set:
        """Extract multi-word capitalized sequences (likely proper nouns / domain terms)."""
        phrases: set = set()
        # Match runs of 2-3 consecutive Title-Case or ALL-CAPS words
        for match in re.finditer(
            r"\b([A-Z][a-zA-Z0-9-]*(?:\s+[A-Z][a-zA-Z0-9-]*){1,2})\b", text
        ):
            phrase = match.group(1).lower().strip()
            # Filter generic single-word capitals (sentence starters etc.)
            if len(phrase) > 4 and phrase not in self.stopwords:
                phrases.add(phrase)
        return phrases

    def _is_temporal_query(self, query: str) -> bool:
        """Return True when the query is oriented toward recency or future steps."""
        lowered = query.strip().lower()
        temporal_markers = (
            "next steps",
            "planned",
            "upcoming",
            "latest",
            "most recent",
            "current status",
            "what's next",
            "whats next",
            "going forward",
            "after that",
            "follow-up",
            "follow up",
        )
        return any(marker in lowered for marker in temporal_markers)

    def _extract_from_sources(self, sources: List[Dict[str, Any]]) -> set:
        terms = set()
        for src in sources:
            terms.update(self._extract_terms(src.get("filename", "")))
            snippet = src.get("snippet", "")
            terms.update(self._extract_terms(snippet))
            terms.update(self._extract_named_phrases(snippet))
        return terms

    def _vector_has_docs(self, vector_data: Any) -> bool:
        if not isinstance(vector_data, dict):
            return False
        docs = vector_data.get("documents", [[]])[0]
        return bool(docs)

    def _looks_like_single_note_summary_query(self, query: str) -> bool:
        if not isinstance(query, str):
            return False
        lowered = query.strip().lower()
        if not lowered:
            return False
        summary_markers = {
            "summary",
            "summarize",
            "point form",
            "point-form",
            "bullet",
            "bullets",
            "notes on",
        }
        title_hints = (
            ".md",
            "book",
            "chapter",
            "how to take smart notes",
        )
        return any(marker in lowered for marker in summary_markers) and any(
            hint in lowered for hint in title_hints
        )

    def _summarize_failure(self, exc: Exception) -> Dict[str, str]:
        return {"error": exc.__class__.__name__, "message": str(exc)}

    async def _post_stage(
        self,
        client: httpx.AsyncClient,
        stage_name: str,
        url: str,
        payload: Dict[str, Any],
        timeout: float,
    ) -> Dict[str, Any]:
        stage_info: Dict[str, Any] = {
            "name": stage_name,
            "url": url,
            "payload": payload,
            "status": "pending",
        }
        try:
            response = await client.post(
                url,
                json=payload,
                timeout=timeout,
                headers=self._service_headers(),
            )
            stage_info["http_status"] = response.status_code
            if response.status_code == 200:
                stage_info["status"] = "ok"
                stage_info["data"] = response.json()
            else:
                stage_info["status"] = "http_error"
                stage_info["data"] = {}
        except Exception as exc:
            stage_info["status"] = "exception"
            stage_info["data"] = {}
            stage_info["error"] = self._summarize_failure(exc)
        return stage_info

    async def _run_internal_stage(
        self,
        stage_name: str,
        payload: Dict[str, Any],
        handler,
    ) -> Dict[str, Any]:
        stage_info: Dict[str, Any] = {
            "name": stage_name,
            "transport": "internal",
            "payload": payload,
            "status": "pending",
        }
        try:
            status_code, data = await asyncio.to_thread(handler, payload)
            stage_info["http_status"] = status_code
            if status_code == 200:
                stage_info["status"] = "ok"
                stage_info["data"] = data if isinstance(data, dict) else {}
            else:
                stage_info["status"] = "http_error"
                stage_info["data"] = data if isinstance(data, dict) else {}
        except Exception as exc:
            stage_info["status"] = "exception"
            stage_info["data"] = {}
            stage_info["error"] = self._summarize_failure(exc)
        return stage_info

    async def retrieve(self, query: str, max_results: int = 10, entities: Optional[List[str]] = None, mem0_context: str = "") -> Dict[str, Any]:
        """
        Orchestrates the staged retrieval pipeline with explicit stage diagnostics.
        """
        stage_debug: Dict[str, Any] = {
            "pipeline": "staged",
            "summary_short_circuit": False,
            "stage_order": [],
            "statuses": {},
            "failures": {},
        }
        graph_stage_timeout = self._graph_stage_timeout_seconds()
        expansion_stage_timeout = self._expansion_stage_timeout_seconds()
        is_multi_facet = has_multi_facet_query(query)
        facets = extract_query_facets(query) if is_multi_facet else []
        facet_count = len(facets)
        # Scale anchor retrieval with detected facet count so each section has coverage
        anchor_n_results = max(5, facet_count * 3) if facet_count > 1 else 5

        async with httpx.AsyncClient() as client:
            notes_payload = {
                "query": query,
                "mode": "graph",
                "n_results": anchor_n_results,
                "max_entities": 15,
                "llm_provider": self.llm_provider,
                "entities": entities,
                "mem0_context": mem0_context,
            }
            if self.llm_model:
                notes_payload["model"] = self.llm_model
            fallback_threshold = min(self.vector_thresholds) if self.vector_thresholds else 0.0
            vec_payload = {
                "query": query,
                "n_results": 5,
                "reranking": False,
                "deduplicate": True,
                "relevance_threshold": fallback_threshold,
                "entities": entities,
                "mem0_context": mem0_context,
            }
            lr_payload = {
                "query": query,
                "mode": "hybrid",
                "llm_provider": self.llm_provider,
            }
            if self.llm_model:
                lr_payload["model"] = self.llm_model

            # Stage 1 + 2 run concurrently: anchor and expansion are independent.
            # Expansion only needs the original query (not anchor results), so parallelising
            # cuts the combined wait time from (anchor + expansion) down to max(anchor, expansion).
            logger.info(
                "Cascading Stage 1+2 parallel: anchor + expansion for '%s'", query
            )
            stage_debug["stage_order"].extend(["anchors", "expansion"])

            async def _run_anchor() -> Dict[str, Any]:
                if self.use_internal_graph_transport:
                    stage = await self._run_internal_stage(
                        "anchors", notes_payload, query_networkx_graph
                    )
                    if stage["status"] != "ok":
                        stage = await self._post_stage(
                            client, "anchors",
                            f"{self.graph_url}/query",
                            notes_payload, graph_stage_timeout,
                        )
                else:
                    stage = await self._post_stage(
                        client, "anchors",
                        f"{self.graph_url}/query",
                        notes_payload, graph_stage_timeout,
                    )
                return stage

            async def _run_expansion() -> Dict[str, Any]:
                if not self._looks_like_single_note_summary_query(query):
                    if self.use_internal_graph_transport:
                        stage = await self._run_internal_stage(
                            "expansion", lr_payload, query_lightrag
                        )
                        if stage["status"] != "ok":
                            stage = await self._post_stage(
                                client, "expansion",
                                f"{self.lightrag_url}/query",
                                lr_payload, expansion_stage_timeout,
                            )
                    else:
                        stage = await self._post_stage(
                            client, "expansion",
                            f"{self.lightrag_url}/query",
                            lr_payload, expansion_stage_timeout,
                        )
                    return stage
                return {"name": "expansion", "status": "skipped_single_note_summary", "data": {}}

            anchor_stage, pre_expansion_stage = await asyncio.gather(
                _run_anchor(), _run_expansion()
            )

            stage_debug["statuses"]["anchors"] = anchor_stage["status"]
            if anchor_stage["status"] == "exception":
                stage_debug["failures"]["anchors"] = anchor_stage.get("error", {})
            notes_data = anchor_stage.get("data", {})
            anchors = []
            if isinstance(notes_data, dict):
                anchors = notes_data.get("sources", []) or []

            logger.info("Cascading Stage 1b: Anchor fallback vector for '%s'", query)
            fallback_stage = None
            if not anchors:
                stage_debug["stage_order"].append("anchor_fallback_vector")
                fallback_stage = await self._post_stage(
                    client,
                    "anchor_fallback_vector",
                    f"{self.embed_url}/query",
                    vec_payload,
                    30.0,
                )
                stage_debug["statuses"]["anchor_fallback_vector"] = fallback_stage["status"]
                if fallback_stage["status"] == "exception":
                    stage_debug["failures"]["anchor_fallback_vector"] = fallback_stage.get("error", {})
                vec_data = fallback_stage.get("data", {})
                if self._vector_has_docs(vec_data):
                    docs = vec_data.get("documents", [[]])[0]
                    metas = vec_data.get("metadatas", [[]])[0]
                    dists = vec_data.get("distances", [[]])[0]
                    for doc, meta, dist in zip(docs, metas, dists):
                        relevance = distance_to_relevance(dist, default=50.0)
                        anchors.append({
                            "filename": meta.get("filename", "unknown"),
                            "filepath": meta.get("filepath", "unknown"),
                            "relevance": relevance,
                            "snippet": (doc[:300] + "...") if len(doc) > 300 else doc,
                        })

            # Entity Extraction from Anchors (after parallel stages complete)
            extracted_entities = set()
            if anchors:
                extracted_entities = self._extract_from_sources(anchors)
            if not extracted_entities:
                extracted_entities = self._extract_terms(query)

            # Process pre-expansion result, applying facet-coverage short-circuit check now
            # that we have anchor results. Because expansion ran in parallel we already have the
            # result — we simply decide whether to use it or discard it.
            expanded_context = {}
            expansion_terms = set()
            expansion_query = query
            expansion_was_skipped = pre_expansion_stage.get("status", "").startswith("skipped")

            if not expansion_was_skipped:
                should_use_expansion = True
                if is_multi_facet and source_set_covers_query_facets(query, anchors):
                    avg_snippet_len = (
                        sum(len(a.get("snippet", "")) for a in anchors) / len(anchors)
                        if anchors else 0
                    )
                    if len(anchors) >= facet_count and avg_snippet_len >= 150:
                        should_use_expansion = False
                        stage_debug["summary_short_circuit"] = True
                        pre_expansion_stage["status"] = "skipped_anchor_facet_coverage"

                stage_debug["statuses"]["expansion"] = pre_expansion_stage["status"]
                if pre_expansion_stage["status"] == "exception":
                    stage_debug["failures"]["expansion"] = pre_expansion_stage.get("error", {})

                if should_use_expansion and pre_expansion_stage.get("status") == "ok":
                    expanded_context = pre_expansion_stage.get("data", {})
                    expanded_text = ""
                    if isinstance(expanded_context, dict):
                        expanded_text = (
                            expanded_context.get("result")
                            or expanded_context.get("answer")
                            or ""
                        )
                    # Ignore LightRAG refusals / no-context responses — they contain only
                    # meta-words (sorry, unable, no-context) that would poison the enhanced query.
                    if expanded_text and not re.search(
                        r"\b(?:sorry|unable|cannot|no[- ]context|don'?t have|not able)\b",
                        expanded_text,
                        re.IGNORECASE,
                    ):
                        expansion_terms = self._extract_terms(expanded_text)
            else:
                stage_debug["summary_short_circuit"] = True
                stage_debug["statuses"]["expansion"] = pre_expansion_stage.get(
                    "status", "skipped"
                )

            # Stage 3: Context-Aware Vector Search
            #
            # Query candidates strategy:
            #  1. A short "entity query" distilled from anchor filenames/entities — best for
            #     long instructional queries where the full text embeds poorly against content chunks.
            #  2. The original query (with expand_query=True to generate 6 semantic variations).
            #  3. If expansion terms are available, an enriched version of the entity query.
            #
            # This ordering ensures the short semantic query is tried first, which avoids the
            # common failure mode where a multi-sentence instructional query embeds too far from
            # concise content chunks to clear even the 40% relevance threshold.

            # Build entity query: concise noun phrase from anchor terms
            entity_terms_for_query = sorted(extracted_entities)[:10] if extracted_entities else []
            entity_query = " ".join(entity_terms_for_query) if entity_terms_for_query else query

            # Enhanced query: entity base + expansion hints
            if expansion_terms:
                top_expansion = sorted(expansion_terms)[:5]
                enhanced_query = f"{entity_query} (related: {', '.join(top_expansion)})"
            else:
                enhanced_query = entity_query

            # Enable reranking for multi-facet queries (precision matters) or large result sets
            use_reranking = is_multi_facet or max_results > 7

            # Extended thresholds: fall back to very low threshold if standard ones yield nothing
            extended_thresholds = list(self.vector_thresholds) + [20]

            logger.info("Cascading Stage 3: Vector Search for '%s'", query)
            vector_chunks = {}
            vector_query = None
            attempted_vector_queries: List[Dict[str, Any]] = []
            try:
                # Candidate order: entity query first (short, semantic), then original,
                # then enhanced. This way a long instructional original query doesn't
                # block the short entity query from running first.
                query_candidates = [entity_query]
                if query != entity_query:
                    query_candidates.append(query)
                if enhanced_query not in query_candidates:
                    query_candidates.append(enhanced_query)
                for candidate in query_candidates:
                    for threshold in extended_thresholds:
                        vec_payload_final = {
                            "query": candidate,
                            "n_results": max_results,
                            "reranking": use_reranking,
                            "deduplicate": True,
                            "relevance_threshold": threshold,
                            "expand_query": True,
                        }
                        attempted_vector_queries.append(
                            {"query": candidate, "relevance_threshold": threshold}
                        )
                        vector_stage = await self._post_stage(
                            client,
                            "targeted_vector",
                            f"{self.embed_url}/query",
                            vec_payload_final,
                            30.0,
                        )
                        stage_debug["stage_order"].append("targeted_vector")
                        stage_debug["statuses"]["targeted_vector"] = vector_stage["status"]
                        if vector_stage["status"] == "exception":
                            stage_debug["failures"]["targeted_vector"] = vector_stage.get("error", {})
                        vector_chunks = vector_stage.get("data", {})
                        if self._vector_has_docs(vector_chunks):
                            vector_query = candidate
                            break
                    if vector_query:
                        break
            except Exception as e:
                logger.error(f"Stage 3 vector fail: {e}")
                vector_chunks = {}
                vector_query = None
                stage_debug["statuses"]["targeted_vector"] = "exception"
                stage_debug["failures"]["targeted_vector"] = self._summarize_failure(e)

            # Stage 4: Synthesis package
            return {
                "query": query,
                "stages": {
                    "anchors": {
                        "answer": notes_data.get("answer", "")
                        if isinstance(notes_data, dict)
                        else "",
                        "sources": anchors,
                    },
                    "entities": sorted(extracted_entities),
                    "expansion": {
                        "query": expansion_query if extracted_entities else query,
                        "terms": sorted(expansion_terms),
                        "raw": expanded_context,
                    },
                    "vectors": vector_chunks,
                    "vector_query": vector_query,
                    "entity_query": entity_query,
                    "enhanced_query": enhanced_query,
                    "diagnostics": {
                        **stage_debug,
                        "attempted_vector_queries": attempted_vector_queries,
                        "anchor_count": len(anchors),
                        "anchor_n_results": anchor_n_results,
                        "entity_count": len(extracted_entities),
                        "facet_count": facet_count,
                        "is_multi_facet": is_multi_facet,
                        "reranking_enabled": use_reranking,
                    },
                },
                # We return raw data, the API gateway or UI can choose to synthesize it via LLM
                # Or we can do it here if we had an LLM client.
                # Given this is a 'Retriever', returning data is usually cleaner.
            }
