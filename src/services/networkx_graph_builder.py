"""
NetworkX Knowledge Graph Builder for Obsidian Vault (Refactored)

This service builds a structural NetworkX graph from an Obsidian vault,
modeling Notes, Blocks, Tags, and Folders as typed nodes.
It replaces the previous LLM-based extraction with a deterministic file-system scan,
while keeping the LLM-based Query/Agent layer.
"""

import json
import os
import re
import time
import logging
import pickle
import math
import networkx as nx
from src.indexing.frontmatter import extract_frontmatter
from src.indexing.canonical_metadata import build_canonical_metadata, slugify_text
from typing import List, Dict, Any, Optional, Union, Set, Tuple
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import yaml

# Configure logging
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)

# Graph data directory (centralized if OBSIDIAN_RAG_DATA_DIR is set)
_data_dir_env = os.getenv("OBSIDIAN_RAG_DATA_DIR", "").strip()
GRAPH_DATA_DIR = (
    Path(_data_dir_env) / "graph_data"
    if _data_dir_env
    else Path("graph_data")
)
try:
    GRAPH_DATA_DIR.mkdir(exist_ok=True)
except OSError:
    pass


def extract_graph_from_payload(payload: Any) -> nx.Graph | None:
    """Support wrapped graph payloads and raw NetworkX pickles."""
    graph = payload.get("graph") if isinstance(payload, dict) and "graph" in payload else payload
    if isinstance(graph, nx.Graph):
        return graph
    return None


def graph_storage_stats(graph: nx.Graph) -> Dict[str, int]:
    tuple_nodes = 0
    string_nodes = 0
    other_nodes = 0
    note_like_nodes = 0

    for node in graph.nodes():
        if isinstance(node, tuple):
            tuple_nodes += 1
            if node and node[0] in {"note", "pdf"}:
                note_like_nodes += 1
        elif isinstance(node, str):
            string_nodes += 1
        else:
            other_nodes += 1

    return {
        "tuple_nodes": tuple_nodes,
        "string_nodes": string_nodes,
        "other_nodes": other_nodes,
        "note_like_nodes": note_like_nodes,
        "total_nodes": graph.number_of_nodes(),
    }


def is_structural_graph(graph: nx.Graph) -> bool:
    stats = graph_storage_stats(graph)
    return stats["tuple_nodes"] > 0 and stats["note_like_nodes"] > 0


def _graph_candidate_variants(path_like: str | Path) -> List[Path]:
    path = Path(path_like).expanduser()
    candidates: List[Path] = []

    def _push(candidate: Path) -> None:
        resolved = candidate.expanduser()
        if resolved not in candidates:
            candidates.append(resolved)

    if path.is_dir():
        _push(path / "knowledge_graph.pkl")
        _push(path / "knowledge_graph_full.pkl")
        _push(path / "knowledge_graph_test.pkl")
        return candidates

    _push(path)
    parent = path.parent
    if path.name == "knowledge_graph_full.pkl":
        _push(parent / "knowledge_graph.pkl")
        _push(parent / "knowledge_graph_test.pkl")
    elif path.name == "knowledge_graph.pkl":
        _push(parent / "knowledge_graph_full.pkl")
        _push(parent / "knowledge_graph_test.pkl")
    elif path.name == "knowledge_graph_test.pkl":
        _push(parent / "knowledge_graph.pkl")
        _push(parent / "knowledge_graph_full.pkl")
    return candidates


def rank_graph_candidate(path_like: str | Path) -> Tuple[float, Dict[str, Any]]:
    path = Path(path_like).expanduser()
    info: Dict[str, Any] = {
        "path": path,
        "exists": path.exists(),
        "valid": False,
        "is_structural": False,
        "stats": {},
    }
    if not path.exists() or not path.is_file():
        return (-math.inf, info)

    try:
        with open(path, "rb") as handle:
            payload = pickle.load(handle)
        graph = extract_graph_from_payload(payload)
    except Exception:
        return (-math.inf, info)

    if graph is None:
        return (-math.inf, info)

    stats = graph_storage_stats(graph)
    structural = is_structural_graph(graph)
    info.update(
        {
            "valid": True,
            "graph": graph,
            "stats": stats,
            "is_structural": structural,
        }
    )

    score = 0.0
    if structural:
        score += 10000.0
        score += min(5000.0, float(stats["note_like_nodes"]))
        if path.name == "knowledge_graph.pkl":
            score += 250.0
        elif path.name == "knowledge_graph_full.pkl":
            score += 100.0
    else:
        score += min(500.0, float(stats["string_nodes"]))

    try:
        score += path.stat().st_mtime / 1_000_000_000
    except OSError:
        pass
    return (score, info)


def select_graph_path(candidates: List[str | Path]) -> Path | None:
    expanded: List[Path] = []
    for candidate in candidates:
        if not candidate:
            continue
        for variant in _graph_candidate_variants(candidate):
            if variant not in expanded:
                expanded.append(variant)

    best_path: Path | None = None
    best_score = -math.inf
    for candidate in expanded:
        score, info = rank_graph_candidate(candidate)
        if not info.get("valid"):
            continue
        if score > best_score:
            best_score = score
            best_path = candidate
    return best_path


QUERY_STOPWORDS = {
    "and", "or", "the", "a", "an", "in", "on", "with", "for", "to", "of",
    "from", "by", "is", "are", "was", "were", "be", "been", "it", "this",
    "that", "these", "those", "as", "at", "via", "etc", "my", "me", "i",
    "we", "our", "your", "their", "notes", "note", "about", "does", "do",
    "did", "show", "tell", "explain", "what", "which",
}

CONNECTION_HINTS = (
    "connected", "connection", "connect", "relate", "related", "relationship",
    "path between", "how are", "how is", "linked", "link between", "tie together",
)

TIMELINE_HINTS = (
    "timeline", "sequence", "progression", "history", "before", "after", "follow-up",
    "follow up", "scan", "scans", "trend", "chronology", "over time", "latest", "first",
)

SUMMARY_HINTS = ("summary", "overview", "cluster", "group", "themes")

PHASE_QUERY_HINTS = {
    "chemotherapy": ("r-chop", "chemo", "chemotherapy", "epoch", "fludarabine", "cyclophosphamide"),
    "car_t": ("car-t", "car t", "yescarta", "axi-cel", "kymriah", "infusion"),
    "monitoring": ("scan", "pet", "ct", "mri", "follow-up", "follow up", "surveillance"),
    "progression_assessment": ("progression", "relapse", "refractory"),
}

NODE_KINDS_FOR_RETRIEVAL = {"note", "pdf", "tag", "folder"}
PRIMARY_SOURCE_KINDS = {"note", "pdf"}

class GraphBuilder:
    """Build structural knowledge graph from Obsidian vault"""
    
    def __init__(self, api_key: Optional[str] = None):
        # API key is kept for compatibility but not used in structural build
        self.graph = nx.MultiDiGraph()
        self.processed_files = set()
        self._canonical_nodes: Dict[str, List[tuple]] = {}
        self._skip_same_as_ids = {"index", "readme", "notes", "summary", "overview"}
        self.stats = {
            'notes': 0,
            'tags': 0,
            'folders': 0,
            'edges': 0,
            'errors': 0
        }

    def _sanitize_content(self, content: str) -> str:
        """Strip Obsidian specific syntax artifacts"""
        if not content: return ""
        # Remove comments
        content = re.sub(r'%%.*?%%', '', content, flags=re.DOTALL)
        # Remove block refs
        content = re.sub(r'\s\^[a-zA-Z0-9-]+$', '', content, flags=re.MULTILINE)
        return content

    def build_structure(self, vault_path: str):
        """
        Scan the vault and build the graph.
        
        Node types:
          ("note", file_path)
          ("tag", tag_name)
          ("folder", folder_path)
          ("block", block_id) [Optional, basic support]
        
        Edge types:
          LINK: note -> note (Wikilinks)
          TAGGED_AS: note -> tag
          IN_FOLDER: note -> folder
          INHERITS_FOLDER: folder -> parent_folder
        """
        vault_root = Path(vault_path)
        if not vault_root.exists():
            raise FileNotFoundError(f"Vault path not found: {vault_path}")

        logger.info(f"Scanning vault at {vault_path}...")
        self._canonical_nodes = {}
        
        # 1. Walk files and create Note/Folder nodes
        for root, dirs, files in os.walk(vault_path):
            rel_root = os.path.relpath(root, vault_path)
            if rel_root == ".":
                rel_root = ""
                
            # Create folder node (unless root)
            if rel_root:
                self._add_folder_node(rel_root)
                # Link to parent folder
                parent_folder = os.path.dirname(rel_root)
                if parent_folder:
                    self._add_folder_node(parent_folder)
                    self.graph.add_edge(
                        ("folder", parent_folder), 
                        ("folder", rel_root), 
                        kind="INHERITS_FOLDER"
                    )
                    self.stats['edges'] += 1

            for filename in files:
                if filename.startswith("."): continue
                
                file_path = os.path.join(root, filename)
                rel_path = os.path.join(rel_root, filename)
                
                if filename.lower().endswith(".md"):
                    self._process_markdown_file(file_path, rel_path, rel_root)
                elif filename.lower().endswith(".pdf"):
                    self._process_pdf_file(file_path, rel_path, rel_root)
                else:
                    # Optional: Add non-md files as generic file nodes or attachment nodes
                    pass

        logger.info(f"Graph build complete: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
        self._add_same_as_edges()

    def _register_canonical_node(self, canonical_id: str, node_id: tuple) -> None:
        cid = slugify_text(canonical_id)
        if not cid or cid in self._skip_same_as_ids:
            return
        self._canonical_nodes.setdefault(cid, []).append(node_id)

    def _add_same_as_edges(self) -> None:
        same_as_edges = 0
        for canonical_id, nodes in self._canonical_nodes.items():
            unique_nodes = sorted(set(nodes), key=lambda node: str(node))
            if len(unique_nodes) < 2:
                continue

            canonical_node = min(
                unique_nodes,
                key=lambda node: (
                    len(str(node[1])) if isinstance(node, tuple) else len(str(node)),
                    str(node),
                ),
            )
            canonical_path = canonical_node[1] if isinstance(canonical_node, tuple) else str(canonical_node)
            canonical_node_data = self.graph.nodes[canonical_node]
            canonical_node_data["canonical_id"] = canonical_id
            canonical_node_data["is_canonical"] = True
            canonical_node_data["canonical_target"] = canonical_path

            for node_id in unique_nodes:
                node_data = self.graph.nodes[node_id]
                node_data["canonical_id"] = canonical_id
                node_data["canonical_target"] = canonical_path
                if node_id == canonical_node:
                    continue
                self.graph.add_edge(node_id, canonical_node, kind="SAME_AS", reason="canonical_id_match")
                same_as_edges += 1
                self.stats["edges"] += 1

        if same_as_edges:
            logger.info("Linked %s duplicate nodes using SAME_AS", same_as_edges)

    def _add_folder_node(self, folder_path: str):
        node_id = ("folder", folder_path)
        if not self.graph.has_node(node_id):
            self.graph.add_node(node_id, name=os.path.basename(folder_path), path=folder_path)
            self.stats['folders'] += 1

    def _process_pdf_file(self, full_path: str, rel_path: str, folder_path: str):
        """Process PDF file as a graph node"""
        try:
            node_id = ("pdf", rel_path)
            stat_info = os.stat(full_path)
            
            attrs = {
                "title": Path(rel_path).stem.replace('_', ' ').title(), # Better title from filename
                "path": rel_path,
                "mtime": stat_info.st_mtime,
                "ctime": stat_info.st_ctime,
                "tags": ["#pdf"], # Explicit tag for graph queries
                "type": "pdf"
            }
            canonical_meta = build_canonical_metadata(
                file_path=Path(rel_path),
                metadata={},
                text="",
                tags=attrs.get("tags", []),
                aliases=[],
            )
            attrs.update(
                {
                    "canonical_id": canonical_meta.get("canonical_id", ""),
                    "aliases_normalized": canonical_meta.get("aliases_normalized", []),
                    "entity_type": canonical_meta.get("entity_type", "pdf_document"),
                    "timeline_date": canonical_meta.get("timeline_date", ""),
                    "treatment_phase": canonical_meta.get("treatment_phase", "unspecified"),
                }
            )
            self.graph.add_node(node_id, **attrs)
            self._register_canonical_node(attrs.get("canonical_id", ""), node_id)
            # We track stats in a generic way or add specific counter? 
            # Let's count as 'notes' for general volume or new key?
            # reusing 'notes' might be confusing. Let's add 'pdfs' to stats check or just ignore.
            
            # Edge: IN_FOLDER
            if folder_path:
                self._add_folder_node(folder_path)
                self.graph.add_edge(node_id, ("folder", folder_path), kind="IN_FOLDER")
                self.stats['edges'] += 1
                
        except Exception as e:
            logger.error(f"Error processing PDF {rel_path}: {e}")
            self.stats['errors'] += 1

    def _process_markdown_file(self, full_path: str, rel_path: str, folder_path: str):
        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Parse Frontmatter
            metadata, body = self._parse_frontmatter(content)
            body = self._sanitize_content(body)
            
            # Create Note Node
            node_id = ("note", rel_path)
            stat_info = os.stat(full_path)
            
            attrs = {
                "title": metadata.get("title", Path(rel_path).stem),
                "path": rel_path,
                "mtime": stat_info.st_mtime,
                "ctime": stat_info.st_ctime,
                "tags": metadata.get("tags", []),
                "aliases": metadata.get("aliases", []),
                "frontmatter": metadata
            }
            canonical_meta = build_canonical_metadata(
                file_path=Path(rel_path),
                metadata=metadata,
                text=body,
                tags=attrs.get("tags", []),
                aliases=attrs.get("aliases", []),
            )
            attrs.update(
                {
                    "canonical_id": canonical_meta.get("canonical_id", ""),
                    "aliases_normalized": canonical_meta.get("aliases_normalized", []),
                    "entity_type": canonical_meta.get("entity_type", "note"),
                    "timeline_date": canonical_meta.get("timeline_date", ""),
                    "treatment_phase": canonical_meta.get("treatment_phase", "unspecified"),
                }
            )
            self.graph.add_node(node_id, **attrs)
            self._register_canonical_node(attrs.get("canonical_id", ""), node_id)
            self.stats['notes'] += 1
            
            # Edge: IN_FOLDER
            if folder_path:
                self._add_folder_node(folder_path)
                self.graph.add_edge(node_id, ("folder", folder_path), kind="IN_FOLDER")
                self.stats['edges'] += 1
            
            # Process Tags (Frontmatter)
            labels = attrs["tags"]
            if isinstance(labels, list):
                for tag in labels:
                    self._add_tag_edge(node_id, tag)
            elif isinstance(labels, str):
                 for tag in labels.split(","):
                    self._add_tag_edge(node_id, tag.strip())

            # Process Body: Wikilinks and Inline Tags
            self._scan_links_and_tags(node_id, body)
            
        except Exception as e:
            logger.error(f"Error processing file {rel_path}: {e}")
            self.stats['errors'] += 1

    def _parse_frontmatter(self, content: str) -> Tuple[Dict, str]:
        """Wrapper for shared frontmatter utility"""
        return extract_frontmatter(content)

    def _add_tag_edge(self, source_node, tag_name: str):
        if not tag_name: return
        # Normalize tag
        tag_name = tag_name if tag_name.startswith("#") else f"#{tag_name}"
        tag_node = ("tag", tag_name)
        
        if not self.graph.has_node(tag_node):
            self.graph.add_node(tag_node, name=tag_name)
            self.stats['tags'] += 1
            
        self.graph.add_edge(source_node, tag_node, kind="TAGGED_AS")
        self.stats['edges'] += 1

    def _scan_links_and_tags(self, source_node: tuple, text: str):
        # Regex for standard Wikilinks [[target]] or [[target|alias]]
        link_pattern = re.compile(r"\[\[([^\]\|]+)(\|[^\]]+)?\]\]")
        tag_pattern = re.compile(r"(?<=[\s^])#([a-zA-Z0-9_\-/]+)")
        
        # Find Links
        for match in link_pattern.finditer(text):
            target_raw = match.group(1)
            target_id = self._resolve_link(target_raw)
            if target_id:
                self.graph.add_edge(source_node, target_id, kind="LINK", raw_target=target_raw)
                self.stats['edges'] += 1

        # Find Tags
        for match in tag_pattern.finditer(text):
            tag_name = match.group(1)
            self._add_tag_edge(source_node, tag_name)

    def _resolve_link(self, target_raw: str) -> Optional[Tuple[str, str]]:
        cleaned = target_raw.split('#')[0].strip()
        if not cleaned: return None
        
        # If it has an extension, keep it. If not, assume .md
        # This allows linking to [[Scan.pdf]] as ("note", "Scan.pdf") or ("pdf", "Scan.pdf")?
        # IMPORTANT: Our Node Types distinguish ("note", path) vs ("pdf", path).
        # We need to guess the type OR use a generic ("file", path) reference?
        # But we built the graph with specific types.
        # If we return ("note", "Scan.pdf"), it won't match the ("pdf", "Scan.pdf") node we created!
        
        ext = os.path.splitext(cleaned)[1].lower()
        if ext == '.pdf':
            return ("pdf", cleaned)
        elif not ext:
             cleaned += ".md"
             return ("note", cleaned)
        else:
             # Other extensions? Treat as note or generic file? 
             # For now fallback to 'note' ID but with original extension if present?
             # Or force md? Obsidian usually omits extension for MD.
             pass
             
        return ("note", cleaned)

    def save_graph(self, filepath: str = None):
        """Save graph to disk"""
        if filepath is None: filepath = str(GRAPH_DATA_DIR / "knowledge_graph.pkl")
        file_path = Path(filepath)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'wb') as f:
            pickle.dump({
                'graph': self.graph,
                'stats': self.stats,
                'timestamp': datetime.now().isoformat()
            }, f)

    def load_graph(self, filepath: str = None):
        """Load graph from disk"""
        if filepath is None: filepath = str(GRAPH_DATA_DIR / "knowledge_graph.pkl")
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
            if isinstance(data, dict) and 'graph' in data:
                self.graph = data['graph']
                self.stats = data.get('stats', {})
            elif isinstance(data, (nx.MultiDiGraph, nx.DiGraph)):
                self.graph = data
            else:
                raise ValueError(f"Unknown graph file format: {type(data)}")

class GraphQuerier:
    """Query the knowledge graph (LLM-enabled)"""
    
    def __init__(self, graph_builder: GraphBuilder, api_key: Optional[str] = None):
        self.graph = graph_builder.graph
        self.api_key = (
            api_key
            or os.environ.get("GRAPH_LLM_API_KEY")
            or os.environ.get("OPENROUTER_API_KEY")
        )
        self.base_url = os.environ.get(
            "GRAPH_LLM_BASE_URL", "https://openrouter.ai/api/v1"
        )
        try:
            from openai import OpenAI
            if self.api_key:
                self.client = OpenAI(
                    base_url=self.base_url,
                    api_key=self.api_key,
                )
            else:
                self.client = None
        except ImportError:
            self.client = None
            
        self.model = (
            os.environ.get("GRAPH_MODEL")
            or os.environ.get("OPENROUTER_MODEL")
            or os.environ.get("LIGHTRAG_MODEL")
            or os.environ.get("KIMI_MODEL")
            or "openrouter/auto"
        )
        self._build_index()
        self._undirected_graph = self.graph.to_undirected(as_view=True)
        self._path_graph = self._build_path_graph()
        self._build_retrieval_records()
        self.last_retrieval_debug: Dict[str, Any] = {}

    def _canonical_node_for(self, node_id: tuple | str):
        if not isinstance(node_id, tuple):
            return node_id
        node_data = self.graph.nodes[node_id] if self.graph.has_node(node_id) else {}
        canonical_target = str(node_data.get("canonical_target", "")).strip()
        if not canonical_target:
            return node_id
        kind = node_id[0]
        canonical_node = (kind, canonical_target)
        if self.graph.has_node(canonical_node):
            return canonical_node
        return node_id

    def _build_index(self):
        """Build mapping from string names to Nodes"""
        self.index = {}
        self._canonical_lookup = {}
        for node in self.graph.nodes(data=True):
            nid, attrs = node
            canonical_nid = self._canonical_node_for(nid)
            self._canonical_lookup[nid] = canonical_nid
            if isinstance(nid, tuple):
                 kind, val = nid
                 keys = [val]
                 if kind == "note":
                     keys.append(Path(val).stem)
                     if attrs.get('aliases'):
                         keys.extend(attrs['aliases'])
                     if attrs.get('aliases_normalized'):
                         keys.extend(attrs['aliases_normalized'])
                     if attrs.get('canonical_id'):
                         keys.append(attrs['canonical_id'])
                 elif kind == "tag":
                     keys.append(val.lstrip("#"))
                 elif kind == "folder":
                     keys.append(Path(val).name)
                 elif kind == "pdf":
                     keys.append(Path(val).name)
                     if attrs.get('canonical_id'):
                         keys.append(attrs['canonical_id'])
            else:
                keys = [str(nid)]
                
            for k in keys:
                k_lower = str(k).lower()
                if k_lower not in self.index:
                    self.index[k_lower] = []
                if canonical_nid not in self.index[k_lower]:
                    self.index[k_lower].append(canonical_nid)

    def _hydrate_node_props(self, node_id, data: Dict) -> Dict:
        """Inject derived properties (like sources) for backward compatibility"""
        if 'sources' not in data:
            data['sources'] = []
            if isinstance(node_id, tuple):
                kind, val = node_id
                if kind == 'note' or kind == 'pdf':
                    data['sources'].append({'filename': val, 'filepath': val})
                elif kind == 'tag' or kind == 'folder':
                     # Find associated notes (limit 10)
                     count = 0
                     for u, v, d in self.graph.in_edges(node_id, data=True):
                         if isinstance(u, tuple) and u[0] == 'note':
                             data['sources'].append({'filename': u[1], 'filepath': u[1]})
                             count += 1
                             if count >= 10: break
        return data

    def _display_name(self, node_id, data: Dict | None = None) -> str:
        props = data or {}
        if props.get("title"):
            return str(props["title"])
        if props.get("name"):
            return str(props["name"])
        if isinstance(node_id, tuple):
            return str(node_id[1])
        return str(node_id)

    def _node_kind(self, node_id) -> str:
        return node_id[0] if isinstance(node_id, tuple) else "unknown"

    def _node_path(self, node_id, data: Dict | None = None) -> str:
        props = data or {}
        if props.get("path"):
            return str(props["path"])
        if isinstance(node_id, tuple):
            return str(node_id[1])
        return str(node_id)

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()

    def _query_terms(self, user_query: str) -> list[str]:
        terms = []
        for term in re.split(r"\W+", str(user_query or "").lower()):
            clean = term.strip()
            if len(clean) < 2 or clean in QUERY_STOPWORDS:
                continue
            if clean not in terms:
                terms.append(clean)
        return terms

    def _infer_retrieval_intent(self, user_query: str) -> Dict[str, Any]:
        lowered = str(user_query or "").lower()
        connection = any(hint in lowered for hint in CONNECTION_HINTS)
        timeline = any(hint in lowered for hint in TIMELINE_HINTS)
        summary = any(hint in lowered for hint in SUMMARY_HINTS)
        if connection:
            kind = "connection"
        elif timeline:
            kind = "timeline"
        elif summary:
            kind = "summary"
        else:
            kind = "lookup"
        return {
            "kind": kind,
            "connection": connection,
            "timeline": timeline,
            "summary": summary,
            "hop_cutoff": 4 if connection else (2 if timeline else 1),
            "path_cutoff": 5 if connection else 3,
            "max_seed_nodes": 6 if connection else 8,
            "max_context_nodes": 10 if connection else 12,
        }

    def _phase_bonus(self, query_lower: str, treatment_phase: str) -> float:
        phase = str(treatment_phase or "").strip().lower()
        if not phase:
            return 0.0
        for target_phase, hints in PHASE_QUERY_HINTS.items():
            if target_phase != phase:
                continue
            if any(hint in query_lower for hint in hints):
                return 2.0
        return 0.0

    def _parse_timeline_sort_key(self, raw_value: str) -> tuple[int, str]:
        value = str(raw_value or "").strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            return (0, value)
        return (1, "")

    def _build_retrieval_records(self) -> None:
        self._retrieval_records: Dict[Any, Dict[str, Any]] = {}
        for node_id, attrs in self.graph.nodes(data=True):
            kind = self._node_kind(node_id)
            if kind not in NODE_KINDS_FOR_RETRIEVAL:
                continue
            display_name = self._display_name(node_id, attrs)
            path_value = self._node_path(node_id, attrs)
            aliases = attrs.get("aliases", []) or []
            aliases_normalized = attrs.get("aliases_normalized", []) or []
            tags = attrs.get("tags", []) or []
            canonical_id = str(attrs.get("canonical_id", "") or "").strip()
            searchable_parts = [
                display_name,
                path_value,
                " ".join(str(a) for a in aliases),
                " ".join(str(a) for a in aliases_normalized),
                " ".join(str(tag) for tag in tags),
                canonical_id,
                str(Path(path_value).stem) if path_value else "",
                str(Path(path_value).parent).replace("\\", "/") if path_value else "",
            ]
            searchable_text = " ".join(part for part in searchable_parts if part).strip()
            self._retrieval_records[node_id] = {
                "kind": kind,
                "title": display_name,
                "path": path_value,
                "searchable_text": searchable_text.lower(),
                "searchable_norm": self._normalize_text(searchable_text),
                "timeline_date": str(attrs.get("timeline_date", "") or "").strip(),
                "treatment_phase": str(attrs.get("treatment_phase", "") or "").strip(),
                "degree": self._undirected_graph.degree(node_id) if self._undirected_graph.has_node(node_id) else 0,
            }

    def _build_path_graph(self) -> nx.Graph:
        path_graph = nx.Graph()
        for node_id in self.graph.nodes():
            if self._node_kind(node_id) in PRIMARY_SOURCE_KINDS:
                path_graph.add_node(node_id)

        for source, target, edge_data in self.graph.edges(data=True):
            source_kind = self._node_kind(source)
            target_kind = self._node_kind(target)
            if source_kind not in PRIMARY_SOURCE_KINDS or target_kind not in PRIMARY_SOURCE_KINDS:
                continue
            edge_kind = str(edge_data.get("kind", "") or "").strip().upper()
            if edge_kind not in {"LINK", "SAME_AS"}:
                continue
            path_graph.add_edge(source, target, kind=edge_kind)
        return path_graph

    def _path_quality(self, path: list[Any]) -> tuple[int, int, int]:
        weak_intermediates = 0
        primary_nodes = 0
        for node_id in path:
            kind = self._node_kind(node_id)
            if kind in PRIMARY_SOURCE_KINDS:
                primary_nodes += 1
            elif kind in {"folder", "tag"}:
                weak_intermediates += 1
        return (-weak_intermediates, primary_nodes, -len(path))

    def _score_seed_nodes(self, user_query: str, query_terms: list[str], intent: Dict[str, Any]) -> list[dict]:
        query_lower = str(user_query or "").lower()
        query_norm = self._normalize_text(user_query)
        scored: list[dict] = []

        for node_id, record in self._retrieval_records.items():
            kind = record["kind"]
            searchable = record["searchable_text"]
            searchable_norm = record["searchable_norm"]
            if kind not in PRIMARY_SOURCE_KINDS:
                continue

            matched_terms = [term for term in query_terms if re.search(r"\b" + re.escape(term) + r"\b", searchable)]
            exact_phrase = bool(query_norm and query_norm in searchable_norm)
            title_phrase = bool(record["title"] and record["title"].lower() in query_lower)
            path_phrase = bool(record["path"] and record["path"].lower() in query_lower)

            if not matched_terms and not exact_phrase and not title_phrase and not path_phrase:
                continue

            score = float(len(matched_terms) * 4)
            if exact_phrase:
                score += 8.0
            if title_phrase:
                score += 5.0
            if path_phrase:
                score += 3.0
            score += self._phase_bonus(query_lower, record["treatment_phase"])
            if intent["timeline"] and record["timeline_date"]:
                score += 1.5
            degree_penalty = min(float(record["degree"]) * 0.05, 1.5)
            score -= degree_penalty

            scored.append(
                {
                    "node": node_id,
                    "score": score,
                    "matched_terms": matched_terms,
                    "timeline_date": record["timeline_date"],
                    "treatment_phase": record["treatment_phase"],
                }
            )

        scored.sort(
            key=lambda row: (
                row["score"],
                len(row["matched_terms"]),
                self._parse_timeline_sort_key(row["timeline_date"])[0] == 0,
            ),
            reverse=True,
        )
        return scored[: intent["max_seed_nodes"]]

    def _find_connection_paths(self, seed_nodes: list[Any], path_cutoff: int) -> list[list[Any]]:
        if len(seed_nodes) < 2:
            return []

        primary_paths: list[list[Any]] = []
        fallback_paths: list[list[Any]] = []
        seen_primary_paths: set[tuple[str, ...]] = set()
        seen_fallback_paths: set[tuple[str, ...]] = set()
        max_pairs = min(6, len(seed_nodes) * (len(seed_nodes) - 1) // 2)
        pair_count = 0

        for i, source in enumerate(seed_nodes):
            for target in seed_nodes[i + 1 :]:
                if pair_count >= max_pairs:
                    break
                pair_count += 1
                try:
                    path = nx.shortest_path(self._path_graph, source, target)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    path = None

                if path and len(path) - 1 <= path_cutoff:
                    signature = tuple(str(node) for node in path)
                    if signature not in seen_primary_paths:
                        seen_primary_paths.add(signature)
                        primary_paths.append(path)
                    continue

                try:
                    fallback_path = nx.shortest_path(self._undirected_graph, source, target)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
                if len(fallback_path) - 1 > path_cutoff:
                    continue
                signature = tuple(str(node) for node in fallback_path)
                if signature in seen_fallback_paths:
                    continue
                seen_fallback_paths.add(signature)
                fallback_paths.append(fallback_path)
            if pair_count >= max_pairs:
                break

        if primary_paths:
            primary_paths.sort(key=lambda path: (len(path), self._path_quality(path)), reverse=False)
            return primary_paths[:4]

        fallback_paths.sort(key=lambda path: (self._path_quality(path), -len(path)), reverse=True)
        return fallback_paths[:4]

    def _rank_context_nodes(
        self,
        seed_rows: list[dict],
        intent: Dict[str, Any],
        query_terms: list[str],
        user_query: str,
    ) -> tuple[list[dict], list[list[Any]]]:
        if not seed_rows:
            return [], []

        seed_nodes = [row["node"] for row in seed_rows]
        seed_score_map = {row["node"]: float(row["score"]) for row in seed_rows}
        candidate_scores: Dict[Any, float] = defaultdict(float)
        candidate_depths: Dict[Any, int] = {}
        candidate_seed_hits: Dict[Any, int] = defaultdict(int)
        candidate_term_hits: Dict[Any, set[str]] = defaultdict(set)
        query_lower = str(user_query or "").lower()

        for seed_row in seed_rows:
            source = seed_row["node"]
            try:
                lengths = nx.single_source_shortest_path_length(
                    self._undirected_graph,
                    source,
                    cutoff=intent["hop_cutoff"],
                )
            except (nx.NetworkXError, nx.NodeNotFound):
                continue
            for node_id, depth in lengths.items():
                kind = self._node_kind(node_id)
                if kind not in NODE_KINDS_FOR_RETRIEVAL:
                    continue
                if kind not in PRIMARY_SOURCE_KINDS and depth > 1:
                    continue

                record = self._retrieval_records.get(node_id)
                if not record:
                    continue

                depth_bonus = max(0.0, 4.0 - (depth * 1.5))
                lexical_bonus = 0.0
                for term in query_terms:
                    if re.search(r"\b" + re.escape(term) + r"\b", record["searchable_text"]):
                        candidate_term_hits[node_id].add(term)
                lexical_bonus += float(len(candidate_term_hits[node_id])) * 1.3
                lexical_bonus += self._phase_bonus(query_lower, record["treatment_phase"])
                if intent["timeline"] and record["timeline_date"]:
                    lexical_bonus += 1.5
                if kind in PRIMARY_SOURCE_KINDS:
                    lexical_bonus += 1.0
                else:
                    lexical_bonus -= 0.5

                candidate_scores[node_id] += (seed_score_map[source] * 0.45) + depth_bonus + lexical_bonus
                candidate_depths[node_id] = min(depth, candidate_depths.get(node_id, depth))
                candidate_seed_hits[node_id] += 1

        connection_paths = self._find_connection_paths(seed_nodes, intent["path_cutoff"]) if intent["connection"] else []
        path_nodes: set[Any] = set()
        for path in connection_paths:
            for node_id in path:
                path_nodes.add(node_id)
                candidate_scores[node_id] += 5.5
                candidate_seed_hits[node_id] += 1

        ranked: list[dict] = []
        for node_id, score in candidate_scores.items():
            record = self._retrieval_records.get(node_id)
            if not record:
                continue
            kind = record["kind"]
            if kind not in NODE_KINDS_FOR_RETRIEVAL:
                continue
            if kind not in PRIMARY_SOURCE_KINDS and node_id not in path_nodes:
                continue

            depth = candidate_depths.get(node_id, intent["hop_cutoff"] + 1)
            multi_seed_bonus = min(float(candidate_seed_hits[node_id] - 1) * 1.5, 4.5)
            final_score = score + multi_seed_bonus
            ranked.append(
                {
                    "node": node_id,
                    "score": final_score,
                    "depth": depth,
                    "path_hit": node_id in path_nodes,
                    "seed_hit_count": candidate_seed_hits[node_id],
                    "term_hit_count": len(candidate_term_hits[node_id]),
                    "timeline_date": record["timeline_date"],
                    "treatment_phase": record["treatment_phase"],
                }
            )

        if intent["timeline"]:
            ranked.sort(
                key=lambda row: (
                    self._parse_timeline_sort_key(row["timeline_date"]),
                    -row["score"],
                    row["depth"],
                )
            )
        else:
            ranked.sort(
                key=lambda row: (
                    row["path_hit"],
                    row["seed_hit_count"],
                    row["term_hit_count"],
                    row["score"],
                    -row["depth"],
                ),
                reverse=True,
            )
        return ranked[: intent["max_context_nodes"]], connection_paths

    def _connection_path_lines(self, connection_paths: list[list[Any]]) -> list[str]:
        lines: list[str] = []
        for path in connection_paths[:4]:
            path_labels = [self._display_name(node_id, self.graph.nodes[node_id]) for node_id in path]
            if path_labels:
                lines.append("  Path: " + " -> ".join(path_labels))
        return lines

    def _serialize_connection_paths(self, connection_paths: list[list[Any]]) -> list[dict]:
        serialized: list[dict] = []
        for path in connection_paths[:4]:
            nodes = []
            for node_id in path:
                attrs = self.graph.nodes[node_id]
                nodes.append(
                    {
                        "entity": self._display_name(node_id, attrs),
                        "kind": self._node_kind(node_id),
                        "path": self._node_path(node_id, attrs),
                    }
                )
            if nodes:
                serialized.append(
                    {
                        "length": max(0, len(nodes) - 1),
                        "nodes": nodes,
                        "display_path": " -> ".join(node["entity"] for node in nodes),
                    }
                )
        return serialized

    def _render_connection_answer(self, serialized_paths: list[dict]) -> str:
        if not serialized_paths:
            return "No explicit note-link path was found in the structural graph for this connection query."

        lines = ["Explicit connection paths found in the structural graph:"]
        for index, path in enumerate(serialized_paths[:4], start=1):
            display_path = str(path.get("display_path", "") or "").strip()
            nodes = path.get("nodes", []) or []
            file_paths = [
                str(node.get("path", "") or "").strip()
                for node in nodes
                if str(node.get("kind", "") or "").lower() in PRIMARY_SOURCE_KINDS
                and str(node.get("path", "") or "").strip()
            ]
            lines.append("")
            lines.append(f"{index}. Path: {display_path}")
            if file_paths:
                lines.append("   Files:")
                for file_path in file_paths:
                    lines.append(f"   - {file_path}")

        lines.append("")
        if len(serialized_paths) == 1:
            lines.append("This is the only explicit path returned for the query.")
        else:
            lines.append(f"Returned {min(len(serialized_paths), 4)} explicit paths.")

        return "\n".join(lines)

    def _legacy_index_matches(self, user_query: str, max_entities: int) -> list[Any]:
        query_lower = str(user_query or "").lower()
        found_nodes = []
        known_names = sorted(list(self.index.keys()), key=len, reverse=True)
        hits = 0
        for name in known_names:
            if len(name) < 3:
                continue
            if re.search(r'\b' + re.escape(name) + r'\b', query_lower):
                found_nodes.extend(self.index[name])
                hits += 1
                if hits >= max_entities:
                    break
        deduped = []
        seen = set()
        for node in found_nodes:
            canonical = self._canonical_node_for(node)
            if canonical in seen:
                continue
            seen.add(canonical)
            deduped.append(canonical)
        return deduped

    def get_entity_neighborhood(self, entity_query: str, depth: int = 1) -> Dict[str, Any]:
        """Get neighborhood for an entity"""
        entity_query = str(entity_query).strip().strip('"\'')
        nodes = self.index.get(entity_query.lower())
        if not nodes:
            nodes = [n for k, n_list in self.index.items() if entity_query.lower() in k for n in n_list]
            
        if not nodes:
            return {'entity': entity_query, 'found': False}
            
        node_id = self._canonical_node_for(nodes[0])
        data = self.graph.nodes[node_id].copy()
        data = self._hydrate_node_props(node_id, data)
        
        display_name = self._display_name(node_id, data)
        
        result = {
            'entity': display_name,
            'type': node_id[0] if isinstance(node_id, tuple) else 'unknown',
            'found': True,
            'properties': data,
            'outgoing': [],
            'incoming': []
        }
        
        # Outgoing
        for u, v, d in self.graph.out_edges(node_id, data=True):
            target_data = self.graph.nodes[v].copy()
            target_data = self._hydrate_node_props(v, target_data)
            target_name = self._display_name(v, target_data)
            result['outgoing'].append({
                'target': target_name,
                'target_id': str(v),
                'relationship': d.get('kind', 'related'),
                'properties': d
            })
            
        # Incoming
        for u, v, d in self.graph.in_edges(node_id, data=True):
            source_data = self.graph.nodes[u].copy()
            source_data = self._hydrate_node_props(u, source_data)
            source_name = self._display_name(u, source_data)
            result['incoming'].append({
                'source': source_name,
                'source_id': str(u),
                'relationship': d.get('kind', 'related'),
                'properties': d
            })
            
        return result

    def find_paths(self, source: str, target: str, max_depth: int = 3) -> List[List[str]]:
        s_nodes = self.index.get(source.lower())
        t_nodes = self.index.get(target.lower())
        if not s_nodes or not t_nodes: return []
        s, t = s_nodes[0], t_nodes[0]
        try:
            paths = []
            for path in nx.all_simple_paths(self.graph, s, t, cutoff=max_depth):
                str_path = []
                for n in path:
                    if isinstance(n, tuple):
                         str_path.append(n[1])
                    else:
                         str_path.append(str(n))
                paths.append(str_path)
            return paths[:10]
        except:
             return []

    def get_graph_stats(self) -> Dict[str, Any]:
        """Get graph statistics"""
        stats = {
            'nodes': self.graph.number_of_nodes(),
            'edges': self.graph.number_of_edges(),
            'node_types': {}
        }
        
        for node in self.graph.nodes():
            if isinstance(node, tuple):
                kind = node[0]
                stats['node_types'][kind] = stats['node_types'].get(kind, 0) + 1
        
        return stats

    def query_with_llm(
        self,
        user_query: str,
        max_entities: int = 20,
        additional_context: str = "",
        custom_system_prompt: str = "",
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        temperature: float = 0.3,
        llm_caller=None,
    ) -> Tuple[str, List[Dict]]:
        """Query the structural graph using LLM"""
        query_terms = self._query_terms(user_query)
        intent = self._infer_retrieval_intent(user_query)
        seed_rows = self._score_seed_nodes(user_query, query_terms, intent)
        ranked_nodes, connection_paths = self._rank_context_nodes(
            seed_rows,
            intent,
            query_terms,
            user_query,
        )
        if not ranked_nodes:
            ranked_nodes = [
                {
                    "node": node_id,
                    "score": 1.0,
                    "depth": 0,
                    "path_hit": False,
                    "seed_hit_count": 1,
                    "term_hit_count": 1,
                    "timeline_date": "",
                    "treatment_phase": "",
                }
                for node_id in self._legacy_index_matches(user_query, max_entities)
            ]

        context_lines = []
        context_nodes_meta = []
        serialized_paths = self._serialize_connection_paths(connection_paths)
        self.last_retrieval_debug = {
            "intent": intent["kind"],
            "seed_nodes": [
                {
                    "entity": self._display_name(row["node"], self.graph.nodes[row["node"]]),
                    "path": self._node_path(row["node"], self.graph.nodes[row["node"]]),
                    "score": round(float(row["score"]), 3),
                }
                for row in seed_rows
            ],
            "paths": serialized_paths,
        }

        context_lines.append(f"RetrievalIntent: {intent['kind']}")
        if seed_rows:
            seed_labels = [
                self._display_name(row["node"], self.graph.nodes[row["node"]])
                for row in seed_rows[: min(5, len(seed_rows))]
            ]
            context_lines.append("SeedNodes: " + ", ".join(seed_labels))
        if connection_paths:
            context_lines.append("ConnectionPaths:")
            context_lines.extend(self._connection_path_lines(connection_paths))
        context_lines.append("")

        selected_rows = ranked_nodes[: max_entities]
        selected_nodes = {row["node"] for row in selected_rows}

        for row in selected_rows:
            node = row["node"]
            data = self.graph.nodes[node].copy()
            data = self._hydrate_node_props(node, data)
            data["retrieval_score"] = round(float(row["score"]), 3)
            data["retrieval_depth"] = int(row["depth"])
            data["retrieval_path_hit"] = bool(row["path_hit"])
            data["retrieval_seed_hits"] = int(row["seed_hit_count"])
            data["retrieval_term_hits"] = int(row["term_hit_count"])
            data["retrieval_intent"] = intent["kind"]
            node_name = self._display_name(node, data)
            node_type = node[0] if isinstance(node, tuple) else "unknown"
            data["retrieval_node_kind"] = node_type

            context_nodes_meta.append({'entity': node_name, 'properties': data})

            context_lines.append(f"[{node_type.upper()}] {node_name}")
            context_lines.append(
                "  Retrieval: "
                f"score={data['retrieval_score']} depth={data['retrieval_depth']} "
                f"seed_hits={data['retrieval_seed_hits']} path_hit={data['retrieval_path_hit']}"
            )
            if data.get("timeline_date"):
                context_lines.append(f"  Date: {data['timeline_date']}")
            if data.get("treatment_phase") and data.get("treatment_phase") != "unspecified":
                context_lines.append(f"  Phase: {data['treatment_phase']}")
            if 'tags' in data and data['tags']:
                context_lines.append(f"  Tags: {data['tags'][:6]}")

            outs = []
            for u, v, d in self.graph.out_edges(node, data=True):
                if len(outs) >= 4:
                    break
                target_name = self._display_name(v, self.graph.nodes[v])
                if row["path_hit"] or v in selected_nodes:
                    outs.append(f"--({d.get('kind')})-> {target_name}")
            if outs:
                context_lines.append("  " + "\n  ".join(outs[:5]))

            ins = []
            for u, v, d in self.graph.in_edges(node, data=True):
                if len(ins) >= 4:
                    break
                source_name = self._display_name(u, self.graph.nodes[u])
                if row["path_hit"] or u in selected_nodes:
                    ins.append(f"<-({d.get('kind')})-- {source_name}")
            if ins:
                context_lines.append("  " + "\n  ".join(ins[:5]))
            context_lines.append("")

        graph_context = "\n".join(context_lines)
        if not graph_context:
            graph_context = "No direct graph matches found for query terms."

        prompt = f"""You are analyzing a structural Knowledge Graph of a personal Obsidian vault.
        
User Query: {user_query}

Graph Context:
{graph_context}

{additional_context}

Task: Answer the user's question explicitly citing the files/notes and relationships found in the graph.
"""
        if intent["connection"]:
            return self._render_connection_answer(serialized_paths), context_nodes_meta
        try:
            if llm_caller is not None:
                response_text = llm_caller(
                    llm_provider or "openrouter",
                    llm_model or self.model,
                    custom_system_prompt or "You are a helpful knowledge graph assistant.",
                    prompt,
                    temperature,
                )
                return response_text, context_nodes_meta

            if not self.client:
                 return "LLM Client not initialized.", context_nodes_meta

            response = self.client.chat.completions.create(
                model=llm_model or self.model,
                messages=[
                    {"role": "system", "content": custom_system_prompt or "You are a helpful knowledge graph assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=temperature
            )
            return response.choices[0].message.content, context_nodes_meta
        except Exception as e:
            return f"Error querying LLM: {e}", context_nodes_meta

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build Obsidian Knowledge Graph")
    parser.add_argument("--vault", default="/app/vault", help="Path to Obsidian vault")
    parser.add_argument(
        "--output",
        default=str(GRAPH_DATA_DIR / "knowledge_graph_full.pkl"),
        help="Output path",
    )
    
    args = parser.parse_args()
    
    print(f"🚀 Starting NetworkX Graph Builder...")
    print(f"📂 Vault: {args.vault}")
    
    try:
        builder = GraphBuilder()
        builder.build_structure(args.vault)
        builder.save_graph(args.output)
        
        print("\n✅ Graph build complete!")
        print(f"   Notes: {builder.stats['notes']}")
        print(f"   Tags: {builder.stats['tags']}")
        print(f"   Folders: {builder.stats['folders']}")
        print(f"   Edges: {builder.stats['edges']}")
        print(f"   Errors: {builder.stats['errors']}")
        
    except Exception as e:
        print(f"\n❌ Graph build failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
