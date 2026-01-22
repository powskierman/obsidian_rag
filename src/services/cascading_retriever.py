import asyncio
import logging
import os
from typing import List, Dict, Any, Optional
import httpx
import math
import re

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
        api_key: Optional[str] = None,
    ):
        self.embed_url = embed_url
        self.graph_url = graph_url
        self.lightrag_url = lightrag_url
        self.llm_provider = llm_provider
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
        self.vector_thresholds = [75, 60]

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

    async def retrieve(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            # Stage 1: Note Discovery (NetworkX)
            # We search for notes that *title match* or have high vector similarity to the query
            logger.info(f"Stage 1: Note Discovery for '{query}'")

            # Using the graph service's hybrid search but emphasizing note titles/anchors
            # We assume the graph service has a mode or we can just filter its results
            notes_payload = {
                "query": query,
                "mode": "graph",
                "n_results": 5,
                "max_entities": 15,
                "llm_provider": self.llm_provider,
            }
            try:
                notes_resp = await client.post(
                    f"{self.graph_url}/query",
                    json=notes_payload,
                    timeout=30.0,
                    headers=self._service_headers(),
                )
                notes_data = notes_resp.json() if notes_resp.status_code == 200 else {}
            except Exception as e:
                logger.error(f"Stage 1 fail: {e}")
                notes_data = {}

            # Stage 2: Entity Extraction
            # Extract potential entities from the *titles* and *summaries* of found notes
            # Simple heuristic: CamelCase, Uppercase words, or words matching known Tech/Medical patterns
            anchors = []
            if isinstance(notes_data, dict):
                anchors = notes_data.get("sources", []) or []

            # Fallback: if graph mode yields no anchors, use vector search to seed anchors
            if not anchors:
                try:
                    vec_data = {}
                    for threshold in self.vector_thresholds:
                        vec_resp = await client.post(
                            f"{self.embed_url}/query",
                            json={
                                "query": query,
                                "n_results": 5,
                                "reranking": True,
                                "deduplicate": True,
                                "relevance_threshold": threshold,
                            },
                            timeout=30.0,
                            headers=self._service_headers(),
                        )
                        vec_data = (
                            vec_resp.json() if vec_resp.status_code == 200 else {}
                        )
                        if self._vector_has_docs(vec_data):
                            break
                    if self._vector_has_docs(vec_data):
                        docs = vec_data.get("documents", [[]])[0]
                        metas = vec_data.get("metadatas", [[]])[0]
                        dists = vec_data.get("distances", [[]])[0]
                        for doc, meta, dist in zip(docs, metas, dists):
                            try:
                                relevance = max(
                                    0.0, min(100.0, 100 / (1 + math.exp(dist / 2)))
                                )
                            except Exception:
                                relevance = 50.0
                            anchors.append(
                                {
                                    "filename": meta.get("filename", "unknown"),
                                    "filepath": meta.get("filepath", "unknown"),
                                    "relevance": relevance,
                                    "snippet": (doc[:300] + "...")
                                    if len(doc) > 300
                                    else doc,
                                }
                            )
                except Exception as e:
                    logger.error(f"Stage 1 fallback fail: {e}")

            extracted_entities = set()
            if anchors:
                extracted_entities = self._extract_from_sources(anchors)
            if not extracted_entities:
                extracted_entities = self._extract_terms(query)

            # Stage 3: Semantic Expansion (LightRAG)
            # Use the extracted entities to find related concepts in LightRAG
            expanded_context = {}
            expansion_terms = set()
            expansion_query = query
            try:
                expansion_query = " ".join(sorted(extracted_entities)) or query
                logger.info(f"Stage 3: Expanding on '{expansion_query}'")
                lr_payload = {"query": expansion_query, "mode": "hybrid"}
                lr_resp = await client.post(
                    f"{self.lightrag_url}/query",
                    json=lr_payload,
                    timeout=60.0,
                    headers=self._service_headers(),
                )
                if lr_resp.status_code == 200:
                    expanded_context = lr_resp.json()
                    expanded_text = ""
                    if isinstance(expanded_context, dict):
                        expanded_text = (
                            expanded_context.get("result")
                            or expanded_context.get("answer")
                            or ""
                        )
                    expansion_terms = self._extract_terms(expanded_text)
            except Exception as e:
                logger.error(f"Stage 3 fail: {e}")

            # Stage 4: Context-Aware Vector Search
            # Enhance query with findings
            # For simplicity, we just do a robust vector search now, maybe with the expanded terms
            combined_terms = []
            for term in list(extracted_entities | expansion_terms):
                if term not in combined_terms:
                    combined_terms.append(term)
            combined_terms = combined_terms[:12]
            enhanced_query = (
                query if not combined_terms else f"{query} " + " ".join(combined_terms)
            )

            logger.info(
                f"Stage 4: Vector Search with raw query, fallback to enhanced query if needed"
            )
            try:
                vector_chunks = {}
                vector_query = None
                query_candidates = [query]
                if enhanced_query != query:
                    query_candidates.append(enhanced_query)
                for candidate in query_candidates:
                    for threshold in self.vector_thresholds:
                        vec_payload = {
                            "query": candidate,
                            "n_results": max_results,
                            "reranking": True,
                            "deduplicate": True,
                            "relevance_threshold": threshold,
                        }
                        vec_resp = await client.post(
                            f"{self.embed_url}/query",
                            json=vec_payload,
                            timeout=30.0,
                            headers=self._service_headers(),
                        )
                        vector_chunks = (
                            vec_resp.json() if vec_resp.status_code == 200 else {}
                        )
                        if self._vector_has_docs(vector_chunks):
                            vector_query = candidate
                            break
                    if vector_query:
                        break
            except Exception as e:
                logger.error(f"Stage 4 fail: {e}")
                vector_chunks = {}
                vector_query = None

            # Stage 5: Synthesis package
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
                },
                # We return raw data, the API gateway or UI can choose to synthesize it via LLM
                # Or we can do it here if we had an LLM client.
                # Given this is a 'Retriever', returning data is usually cleaner.
            }
