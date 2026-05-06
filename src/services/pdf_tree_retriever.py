"""Retriever over persisted PDF tree indexes."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Sequence

from src.models.pdf_tree import PdfTreeIndex, PdfTreeNode
from src.services.pdf_tree_store import PdfTreeStore

if TYPE_CHECKING:
    from src.services.pdf_tree_chat_providers import ChatProvider


@dataclass
class PdfTreeEvidence:
    source_type: str
    path: str
    title: str
    section: str
    page_start: int
    page_end: int
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_source(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "sourceType": "direct-excerpt",
            "sourceCategory": "vault",
            "filename": self.path.split("/")[-1] if self.path else self.title,
            "filepath": self.path,
            "relevance": max(0.0, min(100.0, self.score * 100.0)),
            "snippet": self.text,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "section": self.section,
            "metadata": self.metadata,
        }


def _terms(value: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", str(value or ""))
        if token.lower() not in {"the", "and", "for", "with", "from", "that", "this", "what", "where", "when"}
    }


def _node_text(index: PdfTreeIndex, node: PdfTreeNode, *, max_chars: int | None = None) -> str:
    chunks = [
        page.text
        for page in index.pages
        if node.page_start <= page.page_number <= node.page_end and page.text.strip()
    ]
    text = "\n\n".join(chunks).strip() or node.text_preview
    if max_chars is None:
        return text.rstrip()
    return text[:max_chars].rstrip()


def _walk_nodes(node: PdfTreeNode) -> list[PdfTreeNode]:
    out = [node]
    for child in node.children:
        out.extend(_walk_nodes(child))
    return out


def _needs_adjacent_context(query: str) -> bool:
    lowered = str(query or "").lower()
    sequence_markers = (
        "before",
        "during",
        "after",
        "install",
        "installation",
        "procedure",
        "process",
        "steps",
        "timeline",
        "expect",
        "recovery",
        "follow-up",
        "follow up",
        "discharge",
        "connect",
        "connection",
        "harness",
        "route",
        "routing",
        "mount",
        "mounting",
        "test",
        "testing",
    )
    return sum(1 for marker in sequence_markers if marker in lowered) >= 2


def _prefers_forward_sequence_context(query: str) -> bool:
    lowered = str(query or "").lower()
    return (
        "after" in lowered
        or "recovery" in lowered
        or "follow-up" in lowered
        or "follow up" in lowered
        or "discharge" in lowered
    ) and ("before" in lowered or "during" in lowered or "procedure" in lowered)


def _is_broad_summary_query(query: str) -> bool:
    lowered = str(query or "").lower()
    summary_markers = ("main", "summary", "overview", "important", "key")
    breadth_markers = ("terms", "limitations", "responsibilities", "fees", "charges", "cancellation", "legal", "conditions")
    return any(marker in lowered for marker in summary_markers) and sum(
        1 for marker in breadth_markers if marker in lowered
    ) >= 2


def _is_navigation_node(node: PdfTreeNode, text: str | None = None) -> bool:
    haystack = f"{node.title}\n{node.text_preview}\n{text or ''}".lower()
    if re.search(r"\b(contents|table of contents|index)\b", haystack):
        return True
    dot_leader_lines = sum(1 for line in haystack.splitlines() if "..." in line and re.search(r"\d\s*$", line))
    numbered_heading_lines = sum(1 for line in haystack.splitlines() if re.match(r"\s*\d+(?:\.\d+)+\s+\S+", line))
    numbered_toc_lines = sum(1 for line in haystack.splitlines() if re.match(r"\s*\d+\.\s+\S+.*\s+\d+\s*$", line))
    return dot_leader_lines >= 3 or (dot_leader_lines >= 1 and numbered_heading_lines >= 3) or numbered_toc_lines >= 4


def _is_cover_node(node: PdfTreeNode, text: str | None = None) -> bool:
    haystack = f"{node.title}\n{node.text_preview}\n{text or ''}".strip()
    if node.page_start > 1 or node.page_end > 1:
        return False
    if len(_terms(haystack)) > 14:
        return False
    lowered = haystack.lower()
    return any(marker in lowered for marker in ("terms of service", "manual", "guide", "important information"))


def _is_low_value_node(node: PdfTreeNode, text: str | None = None) -> bool:
    return _is_navigation_node(node, text) or _is_cover_node(node, text)


class PdfTreeRetriever:
    def __init__(
        self,
        store: PdfTreeStore,
        *,
        provider: ChatProvider | None = None,
        max_documents: int = 3,
        max_nodes_inspected: int = 12,
        max_evidence: int = 5,
        max_chars_per_evidence: int = 1800,
        include_trace: bool = False,
    ) -> None:
        self.store = store
        self.provider = provider
        self.max_documents = max(1, max_documents)
        self.max_nodes_inspected = max(1, max_nodes_inspected)
        self.max_evidence = max(1, max_evidence)
        self.max_chars_per_evidence = max(200, max_chars_per_evidence)
        self.include_trace = include_trace

    async def retrieve(
        self,
        query: str,
        *,
        document_ids: Sequence[str] | None = None,
        source_paths: Sequence[str] | None = None,
    ) -> list[PdfTreeEvidence]:
        candidates = self._load_candidates(document_ids=document_ids, source_paths=source_paths)
        all_evidence: list[PdfTreeEvidence] = []
        for index in candidates:
            selected_nodes = await self._select_nodes(query, index)
            all_evidence.extend(self._nodes_to_evidence(query, index, selected_nodes))
        if _needs_adjacent_context(query):
            all_evidence.sort(key=lambda item: (item.path, item.page_start, item.page_end, item.section))
        else:
            all_evidence.sort(key=lambda item: item.score, reverse=True)
        return all_evidence[: self.max_evidence]

    def _load_candidates(
        self,
        *,
        document_ids: Sequence[str] | None,
        source_paths: Sequence[str] | None,
    ) -> list[PdfTreeIndex]:
        ids: list[str] = []
        has_explicit_candidates = bool(document_ids) or bool(source_paths)
        if document_ids:
            ids.extend(str(document_id) for document_id in document_ids)
        if source_paths:
            for path in source_paths:
                entry = self.store.find_by_source_path(path)
                if entry:
                    ids.append(entry.document_id)
        if not ids:
            if has_explicit_candidates:
                return []
            ids.extend(self.store.load_manifest().keys())

        seen: set[str] = set()
        indexes: list[PdfTreeIndex] = []
        for document_id in ids:
            if len(indexes) >= self.max_documents:
                break
            if document_id in seen:
                continue
            seen.add(document_id)
            try:
                indexes.append(self.store.read_index(document_id))
            except FileNotFoundError:
                continue
        return indexes

    async def _select_nodes(self, query: str, index: PdfTreeIndex) -> list[PdfTreeNode]:
        nodes = [node for node in _walk_nodes(index.root) if node.id != "root"]
        ranked = self._rank_nodes(query, index, nodes)
        shortlist = [node for _, node in ranked[: self.max_nodes_inspected]]
        lexical_seeds = self._lexical_seed_nodes(query, ranked)
        if not self.provider or not shortlist:
            if not shortlist:
                return []
            return self._expand_with_adjacent_ranked_nodes(query, lexical_seeds or [shortlist[0]], ranked)

        prompt = {
            "query": query,
            "document": index.title,
            "nodes": [
                {
                    "id": node.id,
                    "title": node.title,
                    "page_start": node.page_start,
                    "page_end": node.page_end,
                    "preview": node.text_preview[:500],
                }
                for node in shortlist
            ],
            "instruction": "Return JSON only: {\"node_ids\":[\"...\"]} for the most relevant nodes.",
        }
        try:
            response = await self.provider.complete(
                [
                    {"role": "system", "content": "Select relevant PDF tree nodes. Return strict JSON only."},
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
                temperature=0,
            )
            selected_ids = self._parse_selected_ids(response)
        except Exception:
            selected_ids = []
        if not selected_ids:
            return self._expand_with_adjacent_ranked_nodes(query, lexical_seeds or [shortlist[0]], ranked)
        by_id = {node.id: node for node in shortlist}
        selected = [by_id[node_id] for node_id in selected_ids if node_id in by_id]
        if not selected:
            return self._expand_with_adjacent_ranked_nodes(query, lexical_seeds or [shortlist[0]], ranked)
        return self._expand_with_adjacent_ranked_nodes(query, selected, ranked)

    def _lexical_seed_nodes(self, query: str, ranked: list[tuple[float, PdfTreeNode]]) -> list[PdfTreeNode]:
        if not _needs_adjacent_context(query):
            for _, node in ranked:
                if not _is_low_value_node(node):
                    return [node]
            return [ranked[0][1]] if ranked else []
        top_score = max((score for score, _ in ranked), default=0.0)
        min_seed_score = top_score * 0.35 if top_score > 0 else 0.0
        seeds: list[PdfTreeNode] = []
        seen_page_ranges: set[tuple[int, int]] = set()
        for score, node in ranked:
            if len(seeds) >= min(3, self.max_evidence):
                break
            page_range = (node.page_start, node.page_end)
            if score < min_seed_score or page_range in seen_page_ranges or _is_low_value_node(node):
                continue
            if seeds:
                seed_pages = {
                    page
                    for seed in seeds
                    for page in range(seed.page_start, seed.page_end + 1)
                }
                if not any(
                    abs(page - seed_page) <= 2
                    for page in range(node.page_start, node.page_end + 1)
                    for seed_page in seed_pages
                ):
                    continue
            seeds.append(node)
            seen_page_ranges.add(page_range)
        return seeds

    def _expand_with_adjacent_ranked_nodes(
        self,
        query: str,
        selected: list[PdfTreeNode],
        ranked: list[tuple[float, PdfTreeNode]],
    ) -> list[PdfTreeNode]:
        expanded: list[PdfTreeNode] = []
        seen_ids: set[str] = set()
        seen_page_ranges: set[tuple[int, int]] = set()

        def add(node: PdfTreeNode) -> None:
            page_range = (node.page_start, node.page_end)
            if (
                len(expanded) < self.max_evidence
                and node.id not in seen_ids
                and page_range not in seen_page_ranges
            ):
                expanded.append(node)
                seen_ids.add(node.id)
                seen_page_ranges.add(page_range)

        for node in selected:
            add(node)

        selected_pages = {
            page
            for node in selected
            for page in range(node.page_start, node.page_end + 1)
        }
        top_score = max((score for score, _ in ranked), default=0.0)
        if top_score > 0:
            min_score = top_score * (0.2 if _is_broad_summary_query(query) else 0.35)
        else:
            min_score = 0.0
        include_low_scoring_adjacent = _needs_adjacent_context(query)
        prefer_forward_adjacent = _prefers_forward_sequence_context(query)
        ranked_by_id = {node.id: score for score, node in ranked}
        ranked_nodes = [node for _, node in ranked]
        anchor_page = min(selected_pages) if selected_pages else 1

        def adjacency_sort_key(node: PdfTreeNode) -> tuple[int, int, int, int]:
            distance = min(
                abs(page - selected_page)
                for page in range(node.page_start, node.page_end + 1)
                for selected_page in selected_pages
            )
            backward_penalty = 1 if prefer_forward_adjacent and node.page_start < anchor_page else 0
            forward_distance = max(0, node.page_start - anchor_page)
            return (backward_penalty, forward_distance if prefer_forward_adjacent else distance, distance, node.page_start)

        adjacent = sorted(
            (
                node for node in ranked_nodes
                if node.id not in seen_ids
                and (node.page_start, node.page_end) not in seen_page_ranges
                and not _is_low_value_node(node)
                and any(
                    abs(page - selected_page) <= 2
                    for page in range(node.page_start, node.page_end + 1)
                    for selected_page in selected_pages
                )
                and (include_low_scoring_adjacent or ranked_by_id.get(node.id, 0.0) >= min_score)
            ),
            key=adjacency_sort_key,
        )
        for node in adjacent:
            add(node)

        for score, node in ranked:
            if expanded and _is_low_value_node(node):
                continue
            if _needs_adjacent_context(query) and expanded:
                expanded_pages = {
                    page
                    for expanded_node in expanded
                    for page in range(expanded_node.page_start, expanded_node.page_end + 1)
                }
                if not any(
                    abs(page - expanded_page) <= 2
                    for page in range(node.page_start, node.page_end + 1)
                    for expanded_page in expanded_pages
                ):
                    continue
            if score >= min_score:
                add(node)
            if len(expanded) >= self.max_evidence:
                break

        return expanded[: self.max_evidence]

    def _rank_nodes(self, query: str, index: PdfTreeIndex, nodes: list[PdfTreeNode]) -> list[tuple[float, PdfTreeNode]]:
        query_terms = _terms(query)
        ranked: list[tuple[float, PdfTreeNode]] = []
        for node in nodes:
            full_text = _node_text(index, node, max_chars=None)
            haystack = f"{node.title} {node.text_preview} {full_text}"
            title_terms = _terms(node.title)
            preview_terms = _terms(node.text_preview)
            full_terms = _terms(full_text)
            node_terms = title_terms | preview_terms | full_terms
            title_overlap = len(query_terms & title_terms)
            preview_overlap = len(query_terms & preview_terms)
            full_overlap = len(query_terms & full_terms)
            coverage = (len(query_terms & node_terms) / len(query_terms)) if query_terms else 0.0
            phrase_bonus = 0.0
            lowered = haystack.lower()
            for term in query_terms:
                if term in lowered:
                    phrase_bonus += 0.04
            for phrase in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*(?:\s+[A-Za-z0-9][A-Za-z0-9_-]*)+", query.lower()):
                if len(phrase.split()) >= 2 and phrase in lowered:
                    phrase_bonus += 0.25

            text_len = len(full_text.strip())
            content_bonus = min(1.25, text_len / 900.0)
            short_cover_penalty = 0.0
            if text_len < 180 and node.page_start <= 2:
                short_cover_penalty = 1.25

            score = (
                full_overlap * 1.25
                + preview_overlap * 0.45
                + title_overlap * 0.25
                + coverage * 1.5
                + phrase_bonus
                + content_bonus
                - short_cover_penalty
            )
            if _is_low_value_node(node, full_text):
                score *= 0.2
            ranked.append((score, node))
        ranked.sort(key=lambda item: (item[0], -item[1].page_start), reverse=True)
        return ranked

    def _nodes_to_evidence(
        self,
        query: str,
        index: PdfTreeIndex,
        nodes: list[PdfTreeNode],
    ) -> list[PdfTreeEvidence]:
        ranked = self._rank_nodes(query, index, nodes)
        max_score = max((score for score, _ in ranked), default=1.0) or 1.0
        evidence: list[PdfTreeEvidence] = []
        seen_page_ranges: set[tuple[int, int]] = set()
        for raw_score, node in ranked:
            page_range = (node.page_start, node.page_end)
            if page_range in seen_page_ranges:
                continue
            seen_page_ranges.add(page_range)
            metadata = {
                "tree_node_id": node.id,
                "document_id": index.document_id,
                "retriever": "pdf_tree",
            }
            if self.include_trace:
                metadata["node_metadata"] = node.metadata
            evidence.append(
                PdfTreeEvidence(
                    source_type="pdf_tree",
                    path=index.source_path,
                    title=index.title,
                    section=node.title,
                    page_start=node.page_start,
                    page_end=node.page_end,
                    text=_node_text(index, node, max_chars=self.max_chars_per_evidence),
                    score=max(0.01, min(1.0, raw_score / max_score)),
                    metadata=metadata,
                )
            )
            if len(evidence) >= self.max_evidence:
                break
        if _needs_adjacent_context(query):
            evidence.sort(key=lambda item: (item.page_start, item.page_end, item.section))
        return evidence

    @staticmethod
    def _parse_selected_ids(response: str) -> list[str]:
        text = str(response or "").strip()
        if not text:
            return []
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                return []
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return []
        ids = data.get("node_ids") if isinstance(data, dict) else None
        if not isinstance(ids, list):
            return []
        return [str(node_id) for node_id in ids if str(node_id).strip()]
