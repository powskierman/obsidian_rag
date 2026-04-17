#!/usr/bin/env python3
"""Eval harness for _is_comprehensive_vault_review_query().

Purpose: decide whether auto-depth routing is reliable enough to expose as the
default for the proposed "Research" mode. If hit-rate across labelled queries
is >= 80% we keep auto; otherwise we expose depth as an explicit dropdown.

The classifier lives in src/services/api_gateway.py (line ~2788). This script
mirrors it verbatim so we don't pull in FastAPI/httpx/etc. at eval time.

Run: python3 Scripts/debug/eval_comprehensive_classifier.py
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import List


# --- MIRRORED FROM src/services/api_gateway.py (lines 2675-2832) ---------------
_REVIEW_QUERY_LEADING_RE = re.compile(
    r"^\s*(?:please\s+)?(?:(?:deep|comprehensive)\s+)?"
    r"(?:review|analy[sz]e|assess|evaluate|summari[sz]e)\s+",
    re.IGNORECASE,
)
_REVIEW_QUERY_TRAILING_RE = re.compile(
    r"\s+(?:using|with|from)\s+(?:only\s+)?(?:evidence|information|context)\s+from\s+(?:my\s+)?vault\b.*$",
    re.IGNORECASE,
)
_REVIEW_COMPOUND_PATTERNS = (
    (re.compile(r"\bpet\s*(?:/|\band\b)?\s*ct\b", re.IGNORECASE), "pet_ct"),
    (re.compile(r"\bblood\s+work\b", re.IGNORECASE), "bloodwork"),
)


def _clean_review_fragment(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip(" \t\r\n,;:.!?"))
    cleaned = re.sub(r"^(?:my|the|all\s+my)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:from|in)\s+(?:my\s+)?vault$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:documents?|docs?|files?)$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _extract_review_facets(query: str) -> List[str]:
    normalized = re.sub(r"\s+", " ", str(query or "").strip())
    if not normalized:
        return []
    working = _REVIEW_QUERY_LEADING_RE.sub("", normalized)
    working = _REVIEW_QUERY_TRAILING_RE.sub("", working)
    working = re.sub(r"\b(?:from|in)\s+(?:my\s+)?vault\b", "", working, flags=re.IGNORECASE)
    working = re.sub(r"\b(?:notes?|documents?|docs?|files?)\s+about\b", "", working, flags=re.IGNORECASE)
    working = working.strip(" ?!.,;:")
    if not working:
        return []
    protected = working
    for pattern, replacement in _REVIEW_COMPOUND_PATTERNS:
        protected = pattern.sub(replacement, protected)
    primary_fragments = [
        fragment.strip()
        for fragment in re.split(r"\s*(?:,|;|\n)\s*", protected)
        if fragment.strip()
    ] or [protected]
    fragments: List[str] = []
    for fragment in primary_fragments:
        parts = [
            part.strip()
            for part in re.split(r"\s+\band\b\s+", fragment, flags=re.IGNORECASE)
            if part.strip()
        ]
        fragments.extend(parts or [fragment])
    restored: List[str] = []
    seen: set = set()
    for fragment in fragments:
        restored_fragment = fragment.replace("pet_ct", "pet ct")
        cleaned = _clean_review_fragment(restored_fragment)
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        restored.append(cleaned)
    return restored


def _is_comprehensive_vault_review_query(query: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(query or "").strip()).lower()
    if not normalized:
        return False
    has_review_signal = any(
        signal in normalized
        for signal in (
            "review ",
            "review my",
            "deep review",
            "comprehensive review",
            "assess ",
            "analyze ",
            "analyse ",
            "evaluate ",
        )
    )
    if not has_review_signal:
        return False
    facets = _extract_review_facets(query)
    has_personal_scope = any(
        marker in normalized
        for marker in (
            " my ",
            "my vault",
            "my notes",
            "from my vault",
            "using only evidence from my vault",
            "all my",
            "entire vault",
        )
    )
    has_comprehensive_scope = any(
        marker in normalized
        for marker in (
            "all my",
            "entire vault",
            "full vault",
            "comprehensive",
            "deep review",
        )
    )
    return bool(
        (has_personal_scope and len(facets) >= 1)
        or len(facets) >= 2
        or has_comprehensive_scope
    )


# --- EVAL SET -----------------------------------------------------------------
# Labelled: True = should route to "full" (vault_review); False = should stay
# "staged" (regular cascading). 50 queries drawn from realistic vault-research
# patterns: medical tracking, project/workflow review, comparative questions,
# quick lookups, and deliberately ambiguous phrasings.

@dataclass
class Case:
    query: str
    expected: bool  # True = comprehensive (full depth); False = staged
    category: str   # for per-bucket reporting


CASES: List[Case] = [
    # --- TRUE positives: clear comprehensive review intent ---
    Case("Review my entire vault on medical history", True, "explicit-comprehensive"),
    Case("Deep review of my notes on AI research", True, "explicit-comprehensive"),
    Case("Comprehensive review of my blood work and PET/CT results", True, "explicit-comprehensive"),
    Case("Analyze all my notes about the MLX project", True, "explicit-comprehensive"),
    Case("Assess my vault on treatment decisions", True, "explicit-comprehensive"),
    Case("Evaluate my notes on lymphoma treatment options", True, "explicit-comprehensive"),
    Case("Review my notes on home automation and energy usage", True, "multi-facet-personal"),
    Case("Analyze my notes about diet, exercise, and sleep", True, "multi-facet-personal"),
    Case("Assess my notes on cancer treatment, side effects, and outcomes", True, "multi-facet-personal"),
    Case("Review my journal entries on anxiety and coping strategies", True, "multi-facet-personal"),
    Case("Deep review of my vault", True, "comprehensive-only"),
    Case("Comprehensive review of recent symptoms", True, "comprehensive-marker"),
    Case("Review my PET/CT and bloodwork trends", True, "multi-facet-personal"),
    Case("Analyze my vault for Obsidian RAG architecture decisions", True, "personal-scope-single-facet"),
    Case("Evaluate my project notes and meeting summaries", True, "multi-facet-personal"),
    Case("Please review my vault on cardiac medications", True, "personal-scope-single-facet"),
    Case("Review my notes on python tooling, CI setup, and deploy scripts", True, "multi-facet-personal"),
    Case("Analyze my vault comprehensively on research reading", True, "comprehensive-marker"),
    Case("Do a deep review of treatment side effects", True, "comprehensive-marker"),
    Case("Assess my entire vault for gaps in documentation", True, "explicit-comprehensive"),

    # --- TRUE negatives: should NOT trigger comprehensive path ---
    Case("What does chemo do to platelets?", False, "quick-lookup"),
    Case("Summarize the latest PET/CT scan", False, "single-note-summary"),
    Case("Find my notes about lymphoma staging", False, "simple-retrieval"),
    Case("How does LightRAG expand entities?", False, "factual-question"),
    Case("What is the difference between cascading and vector search?", False, "comparison"),
    Case("Show me recent journal entries", False, "simple-retrieval"),
    Case("Who is Dr. Smith?", False, "entity-lookup"),
    Case("When did I start treatment?", False, "factual-question"),
    Case("Last blood test results", False, "quick-lookup"),
    Case("Explain embedding normalization", False, "factual-question"),
    Case("Tell me about the MLX implementation plan", False, "single-topic-summary"),
    Case("What meds am I on?", False, "simple-retrieval"),
    Case("Find notes tagged #research", False, "tag-search"),
    Case("Which day had the highest heart rate?", False, "factual-question"),
    Case("Link between exercise and mood in my notes", False, "correlation-lookup"),
    Case("Recent mentions of side effects", False, "simple-retrieval"),
    Case("How many patients in the trial?", False, "factual-question"),
    Case("Summarize today's journal", False, "single-note-summary"),
    Case("What's on my todo list?", False, "simple-retrieval"),
    Case("Is there a note about the Whistler trip?", False, "existence-check"),

    # --- Ambiguous / trap cases: classifier likely to struggle ---
    # These are where "auto" falls down. Label = what a user probably *wants*.
    Case("Summarize my entire vault on AI", True, "trap-summarize-comprehensive"),  # uses "summarize" + "entire vault" — review verb path excludes summarize
    Case("Give me an overview of my medical history", True, "trap-overview-no-review-verb"),  # no "review/analyze/assess/evaluate" verb
    Case("Walk me through everything I know about lymphoma", True, "trap-no-review-verb"),
    Case("I want a full picture of my cardiac history", True, "trap-no-review-verb"),
    Case("Deep dive into my notes on Obsidian RAG", True, "trap-deep-dive-not-review"),
    Case("Review the document at meds.md", False, "trap-review-single-doc"),  # "review" verb but single-doc scope
    Case("Analyze this code snippet", False, "trap-analyze-not-vault"),  # "analyze" verb, not vault
    Case("Evaluate the performance of this query", False, "trap-evaluate-not-vault"),
    Case("Assess whether this is correct", False, "trap-assess-not-vault"),
    Case("Review my last entry", False, "trap-review-single-note"),  # "review my" but single-note scope
]


def run() -> int:
    tp = tn = fp = fn = 0
    mistakes: List[tuple[Case, bool]] = []
    per_category: dict = {}

    for case in CASES:
        got = _is_comprehensive_vault_review_query(case.query)
        correct = got == case.expected
        bucket = per_category.setdefault(case.category, [0, 0])  # [correct, total]
        bucket[1] += 1
        if correct:
            bucket[0] += 1
        if case.expected and got:
            tp += 1
        elif not case.expected and not got:
            tn += 1
        elif not case.expected and got:
            fp += 1
            mistakes.append((case, got))
        else:
            fn += 1
            mistakes.append((case, got))

    total = len(CASES)
    hits = tp + tn
    hit_rate = hits / total * 100

    print("=" * 72)
    print("CLASSIFIER EVAL — _is_comprehensive_vault_review_query")
    print("=" * 72)
    print(f"Total cases:  {total}")
    print(f"Correct:      {hits}  ({hit_rate:.1f}%)")
    print(f"  True pos:   {tp}  (correctly routed to 'full')")
    print(f"  True neg:   {tn}  (correctly kept 'staged')")
    print(f"  False pos:  {fp}  (would over-escalate to 'full')")
    print(f"  False neg:  {fn}  (would under-route — user wanted 'full')")
    print()

    pos_total = tp + fn
    neg_total = tn + fp
    precision = tp / (tp + fp) * 100 if (tp + fp) else 0.0
    recall = tp / pos_total * 100 if pos_total else 0.0
    print(f"Precision (of 'full' predictions): {precision:.1f}%")
    print(f"Recall    (of true 'full' cases):  {recall:.1f}%")
    print(f"Specificity (of true 'staged'):    {tn/neg_total*100 if neg_total else 0:.1f}%")
    print()

    print("Per-category accuracy:")
    for cat, (c, t) in sorted(per_category.items()):
        flag = "  " if c == t else " !"
        print(f" {flag} {cat:40s} {c}/{t}")
    print()

    if mistakes:
        print("Misclassifications:")
        for case, got in mistakes:
            arrow = "FP" if got and not case.expected else "FN"
            print(f"  [{arrow}] expected={case.expected!s:5s} got={got!s:5s}  "
                  f"({case.category})  {case.query!r}")
        print()

    print("=" * 72)
    if hit_rate >= 80.0:
        print(f"RESULT: {hit_rate:.1f}% >= 80%  → auto-depth is viable as default")
        exit_code = 0
    else:
        print(f"RESULT: {hit_rate:.1f}% <  80%  → expose depth as explicit dropdown")
        exit_code = 1
    print("=" * 72)
    return exit_code


if __name__ == "__main__":
    sys.exit(run())
