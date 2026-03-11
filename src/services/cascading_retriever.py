import logging
import os
from typing import List, Dict, Any, Optional
import httpx
import re

try:
    from cascading_pipeline import distance_to_relevance
except ImportError:
    from src.services.cascading_pipeline import distance_to_relevance

logger = logging.getLogger(__name__)


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

    def _service_headers(self) -> Dict[str, str]:
        api_key = os.getenv("OBSIDIAN_RAG_API_KEY")
        if not api_key:
            return {}
        return {"X-API-Key": api_key}

    def _extract_terms(self, text: str) -> set:
        tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", text.lower())
        return {t for t in tokens if t not in self.stopwords and not t.isdigit()}

    def _extract_from_sources(self, sources: List[Dict[str, Any]]) -> set:
        terms = set()
        for src in sources:
            terms.update(self._extract_terms(src.get("filename", "")))
            terms.update(self._extract_terms(src.get("snippet", "")))
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
        async with httpx.AsyncClient() as client:
            notes_payload = {
                "query": query,
                "mode": "graph",
                "n_results": 5,
                "max_entities": 15,
                "llm_provider": self.llm_provider,
                "entities": entities,
                "mem0_context": mem0_context,
            }
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

            logger.info("Cascading Stage 1: Anchor retrieval for '%s'", query)
            stage_debug["stage_order"].append("anchors")
            anchor_stage = await self._post_stage(
                client,
                "anchors",
                f"{self.graph_url}/query",
                notes_payload,
                30.0,
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

            # Stage 2: Entity Extraction from Anchors
            extracted_entities = set()
            if anchors:
                extracted_entities = self._extract_from_sources(anchors)
            if not extracted_entities:
                extracted_entities = self._extract_terms(query)

            expanded_context = {}
            expansion_terms = set()
            expansion_query = query
            should_expand = not anchors or not self._looks_like_single_note_summary_query(query)
            if should_expand:
                logger.info("Cascading Stage 2: Expansion retrieval for '%s'", query)
                stage_debug["stage_order"].append("expansion")
                expansion_stage = await self._post_stage(
                    client,
                    "expansion",
                    f"{self.lightrag_url}/query",
                    lr_payload,
                    60.0,
                )
                stage_debug["statuses"]["expansion"] = expansion_stage["status"]
                if expansion_stage["status"] == "exception":
                    stage_debug["failures"]["expansion"] = expansion_stage.get("error", {})
                expanded_context = expansion_stage.get("data", {})
                expanded_text = ""
                if isinstance(expanded_context, dict):
                    expanded_text = expanded_context.get("result") or expanded_context.get("answer") or ""
                expansion_terms = self._extract_terms(expanded_text)
            else:
                stage_debug["summary_short_circuit"] = True
                stage_debug["statuses"]["expansion"] = "skipped_summary_short_circuit"

            # Stage 3: Context-Aware Vector Search
            combined_terms = []
            for term in list(extracted_entities | expansion_terms):
                if term not in combined_terms:
                    combined_terms.append(term)
            combined_terms = combined_terms[:12]
            enhanced_query = query if not combined_terms else f"{query} " + " ".join(combined_terms)

            logger.info("Cascading Stage 3: Vector Search for '%s'", query)
            vector_chunks = {}
            vector_query = None
            attempted_vector_queries: List[Dict[str, Any]] = []
            try:
                query_candidates = [query]
                if enhanced_query != query:
                    query_candidates.append(enhanced_query)
                for candidate in query_candidates:
                    for threshold in self.vector_thresholds:
                        vec_payload_final = {
                            "query": candidate,
                            "n_results": max_results,
                            "reranking": False,
                            "deduplicate": True,
                            "relevance_threshold": threshold,
                            "expand_query": candidate == query,
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
                    "enhanced_query": enhanced_query,
                    "diagnostics": {
                        **stage_debug,
                        "attempted_vector_queries": attempted_vector_queries,
                        "anchor_count": len(anchors),
                        "entity_count": len(extracted_entities),
                    },
                },
                # We return raw data, the API gateway or UI can choose to synthesize it via LLM
                # Or we can do it here if we had an LLM client.
                # Given this is a 'Retriever', returning data is usually cleaner.
            }
