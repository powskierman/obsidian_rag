#!/usr/bin/env python3
"""
Report duplicate conceptual entities in the NetworkX knowledge graph.

By default, groups are based on canonical_id and include note/pdf nodes only.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from src.services.networkx_graph_builder import GraphBuilder


def _load_builder(vault_path: Path, graph_path: Path | None) -> GraphBuilder:
    builder = GraphBuilder()
    if graph_path and graph_path.exists():
        builder.load_graph(str(graph_path))
        return builder
    builder.build_structure(str(vault_path))
    return builder


def _collect_duplicate_groups(builder: GraphBuilder) -> list[dict]:
    groups: dict[str, list[tuple]] = defaultdict(list)
    for node_id, attrs in builder.graph.nodes(data=True):
        if not isinstance(node_id, tuple):
            continue
        if node_id[0] not in {"note", "pdf"}:
            continue
        canonical_id = str(attrs.get("canonical_id", "")).strip().lower()
        if not canonical_id:
            continue
        groups[canonical_id].append(node_id)

    rows = []
    for canonical_id, nodes in groups.items():
        unique_nodes = sorted(set(nodes), key=lambda n: n[1])
        if len(unique_nodes) < 2:
            continue
        same_as_count = 0
        for node_id in unique_nodes:
            for _, _, edge_data in builder.graph.out_edges(node_id, data=True):
                if edge_data.get("kind") == "SAME_AS":
                    same_as_count += 1
        rows.append(
            {
                "canonical_id": canonical_id,
                "count": len(unique_nodes),
                "same_as_edges": same_as_count,
                "nodes": unique_nodes,
            }
        )
    rows.sort(key=lambda row: (-row["count"], row["canonical_id"]))
    return rows


def _write_markdown(groups: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Duplicate Entity Report",
        "",
        f"- Duplicate groups: **{len(groups)}**",
        "",
    ]
    if not groups:
        lines.append("No duplicate conceptual entities detected.")
    else:
        lines.extend(
            [
                "| Canonical ID | Nodes | SAME_AS Edges | Status |",
                "|---|---:|---:|---|",
            ]
        )
        for group in groups:
            status = "linked" if group["same_as_edges"] > 0 else "unlinked"
            lines.append(
                f"| `{group['canonical_id']}` | {group['count']} | {group['same_as_edges']} | {status} |"
            )
        lines.append("")
        lines.append("## Group Details")
        lines.append("")
        for group in groups:
            lines.append(f"### `{group['canonical_id']}` ({group['count']} nodes)")
            lines.append("")
            for node_id in group["nodes"]:
                lines.append(f"- `{node_id[1]}`")
            lines.append("")
            lines.append("- Recommended action: merge or add explicit cross-links if semantically identical.")
            lines.append("")

    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Report duplicate entities in NetworkX graph")
    parser.add_argument(
        "--vault",
        default=None,
        help="Vault path (required if --graph is not provided)",
    )
    parser.add_argument(
        "--graph",
        default="graph_data/knowledge_graph.pkl",
        help="Path to existing graph pickle",
    )
    parser.add_argument(
        "--output",
        default="Documentation/DUPLICATE_ENTITY_REPORT.md",
        help="Output markdown report path",
    )
    args = parser.parse_args()

    graph_path = Path(args.graph) if args.graph else None
    vault_path = Path(args.vault) if args.vault else None
    if (not graph_path or not graph_path.exists()) and not vault_path:
        raise SystemExit("--vault is required when --graph does not exist")

    builder = _load_builder(vault_path if vault_path else Path("."), graph_path)
    groups = _collect_duplicate_groups(builder)

    output_path = Path(args.output)
    _write_markdown(groups, output_path)
    print(f"Wrote duplicate entity report: {output_path} (groups={len(groups)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
