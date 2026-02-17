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
import networkx as nx
from src.indexing.frontmatter import extract_frontmatter
from src.indexing.canonical_metadata import build_canonical_metadata, slugify_text
from typing import List, Dict, Any, Optional, Union, Set, Tuple
from pathlib import Path
from datetime import datetime
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
            self.client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
            )
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
        
        display_name = data.get('title', str(node_id[1] if isinstance(node_id, tuple) else node_id))
        
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
            target_name = target_data.get('title', str(v[1] if isinstance(v, tuple) else v))
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
            source_name = source_data.get('title', str(u[1] if isinstance(u, tuple) else u))
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

    def query_with_llm(self, user_query: str, max_entities: int = 20, additional_context: str = "", custom_system_prompt: str = "") -> Tuple[str, List[Dict]]:
        """Query the structural graph using LLM"""
        query_lower = user_query.lower()
        found_nodes = []
        known_names = sorted(list(self.index.keys()), key=len, reverse=True)
        hits = 0
        for name in known_names:
            if len(name) < 3: continue
            if re.search(r'\b' + re.escape(name) + r'\b', query_lower):
                found_nodes.extend(self.index[name])
                hits += 1
                if hits >= max_entities: break
        found_nodes = [self._canonical_node_for(node) for node in found_nodes]
        found_nodes = list(set(found_nodes))
        
        context_lines = []
        context_nodes_meta = []
        
        for node in found_nodes:
            data = self.graph.nodes[node].copy()
            data = self._hydrate_node_props(node, data)
            
            node_name = data.get('title', str(node[1]))
            node_type = node[0] if isinstance(node, tuple) else "unknown"
            
            context_nodes_meta.append({'entity': node_name, 'properties': data})
            
            context_lines.append(f"[{node_type.upper()}] {node_name}")
            if 'tags' in data and data['tags']:
                context_lines.append(f"  Tags: {data['tags']}")
            
            outs = []
            for u, v, d in self.graph.out_edges(node, data=True):
                target_name = self.graph.nodes[v].get('title', v[1])
                outs.append(f"--({d.get('kind')})-> {target_name}")
            if outs:
                context_lines.append("  " + "\n  ".join(outs[:5]))
            
            ins = []
            for u, v, d in self.graph.in_edges(node, data=True):
                source_name = self.graph.nodes[u].get('title', u[1])
                ins.append(f"<-({d.get('kind')})-- {source_name}")
            if ins:
                context_lines.append("  " + "\n  ".join(ins[:5]))
            context_lines.append("")

        graph_context = "\n".join(context_lines)
        if not graph_context:
            graph_context = "No direct graph matches found for query terms."

        if not self.client:
             return "LLM Client not initialized.", context_nodes_meta

        prompt = f"""You are analyzing a structural Knowledge Graph of a personal Obsidian vault.
        
User Query: {user_query}

Graph Context:
{graph_context}

{additional_context}

Task: Answer the user's question explicitly citing the files/notes and relationships found in the graph.
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": custom_system_prompt or "You are a helpful knowledge graph assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.3
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
