# Obsidian RAG: Progressive Testing Suite (2026 Edition)

This document outlines a series of queries designed to progressively test and validate the various search modes of the Obsidian RAG system, from basic similarity to autonomous deep research.

---

## 1. Mode: `vector` (Surface Scan)
**Objective**: Test raw semantic similarity and retrieval of specific technical fragments.

*   **Query**: *"What are the specific technical requirements for the Gridfinity stylus insert project?"*
*   **Target Backend**: ChromaDB
*   **Expected Outcome**: Precise retrieval of the `gridfinity_stylus_insert_1.py` script or associated technical notes.
*   **Verification**: Check if the snippet includes exact parameters or code logic.

## 2. Mode: `notes` (Structural Relationship)
**Objective**: Validate the NetworkX structural graph mapping (30,162 nodes).

*   **Query**: *"What notes are linked to my oncology Map of Content (MoC) but don't mention Yescarta directly?"*
*   **Target Backend**: NetworkX Graph Service
*   **Expected Outcome**: Discovery of diverse medical notes connected via folder hierarchy or wiki-links rather than keyword matching.
*   **Verification**: Ensure the results are structurally "near" the MoC but semantically distinct from the "Yescarta" keyword.

## 3. Mode: `entities` (Conceptual Bridge)
**Objective**: Test the LightRAG entity-centric extraction (7,235 entities).

*   **Query**: *"What are the common philosophical themes between my engineering notes and my home automation research?"*
*   **Target Backend**: LightRAG Service
*   **Expected Outcome**: Identification of "hidden" conceptual matches (e.g., "efficiency," "systemic design," "modularity") that exist across disparate folders.
*   **Verification**: The response should reference cross-domain connections that were not manually linked.

## 4. Mode: `hybrid` (Unified Synthesis)
**Objective**: Test the synergy of Vector data with Graph context.

*   **Query**: *"Give me a summary of my DLBCL treatment timeline based on my scans and oncologist reports from the last quarter of 2024."*
*   **Target Backend**: ChromaDB + LightRAG + NetworkX
*   **Expected Outcome**: A chronological, cited summary.
*   **Verification**: Proper date extraction (Vector) combined with high-level medical context and relationship analysis (Graph).

## 5. Mode: `dual-graph` (Exploration Focus)
**Objective**: Test the merging of structural and conceptual graphs.

*   **Query**: *"Visualize and explain the connection between my Python development workflows and my project management MOCs."*
*   **Target Backend**: LightRAG + NetworkX
*   **Expected Outcome**: Insights into how "intentional" organization (links) contrasts with "actual" conceptual overlaps.
*   **Verification**: Review the 3D graph visualization for cluster formation.

## 6. Mode: `deep-research` (Master Orchestration)
**Objective**: Stress-test the 5-agent stack (Deep Thinking Agentic System) + Tavily Web Search.

*   **Query**: *"Compare my current oncology progress documented in my vault with the latest 2025/2026 clinical standards for DLBCL follow-up. Are there any discrepancies or new tests I should discuss with my doctor?"*
*   **Target Backend**: All Local Backends + Tavily Web Search + Agentic reasoning loop.
*   **Expected Outcome**: A multi-step research report that synthesizes private vault data with live external clinical standards.
*   **Verification**: Watch the live "thinking" logs for sub-query decomposition, web search results, and self-reflection steps.

---

## Execution Instructions
1.  **Open the Web UI**: Visit `http://localhost:3000`.
2.  **Select Mode**: Use the settings dropdown to set the mode before each query.
3.  **Monitor Logs**: For agentic modes, observe the terminal (or UI sidebar) for the Planner and Policy decisions.
4.  **Confirm Citations**: Verify that every claim in the response is backed by a `[[Note Link]]` or a Web URL.
