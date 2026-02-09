"""
Shared utility for robust frontmatter parsing.
Handles various formats including strict YAML, flow-style lists, and malformed headers.
"""

import re
import yaml
from typing import List, Tuple, Dict, Any

def _dedupe_keep_order(items: List[str]) -> List[str]:
    """Deduplicate a list while preserving original order."""
    seen = set()
    output = []
    for item in items:
        if item not in seen:
            output.append(item)
            seen.add(item)
    return output

def _parse_frontmatter_value(raw_value: str) -> List[str]:
    """Parse a frontmatter value that might be a string, a list, or a flow-style list."""
    value = raw_value.strip()
    if not value:
        return []
        
    # Handle flow-style lists: [a, b, c]
    if value.startswith("[") and value.endswith("]"):
        # Simple split by comma for robust handling even if YAML fails
        try:
            # Try proper YAML loading first for safety with quotes/escapes
            parsed = yaml.safe_load(value)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if item is not None]
        except Exception:
            pass
            
        # Fallback to simple splitting
        items = value[1:-1].split(",")
        return [item.strip().strip("'\"") for item in items if item.strip()]
        
    return [value.strip().strip("'\"")]

def _extract_frontmatter_fields(lines: List[str]) -> Tuple[List[str], List[str]]:
    """
    Robustly extract tags and aliases from frontmatter lines.
    Handles both 'key: value' and nested list formats.
    """
    tags = []
    aliases = []
    in_block = None
    
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped == "---":
            continue
            
        lower = stripped.lower()
        
        # Check for key definition
        if ":" in stripped:
            key, val = stripped.split(":", 1)
            key = key.strip().lower()
            val = val.strip()
            
            if key == "tags" or key == "tag":
                if val: # Inline value
                    tags.extend(_parse_frontmatter_value(val))
                    in_block = None # Reset block if inline
                else:
                    in_block = "tags"
                continue
                
            if key == "aliases" or key == "alias":
                if val:
                    aliases.extend(_parse_frontmatter_value(val))
                    in_block = None
                else:
                    in_block = "aliases"
                continue
                
            # If it's another key, we are out of our blocks
            if not stripped.startswith("-"):
                 in_block = None
        
        # Handle list items for current block
        if in_block == "tags":
            if stripped.startswith("-"):
                val = stripped[1:].strip()
                # Handle quoted values
                val = val.strip("'\"")
                if val:
                    tags.append(val)
                continue
                
        elif in_block == "aliases":
            if stripped.startswith("-"):
                val = stripped[1:].strip()
                val = val.strip("'\"")
                if val:
                    aliases.append(val)
                continue

    return _dedupe_keep_order(tags), _dedupe_keep_order(aliases)

def extract_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    Extract frontmatter metadata and body from markdown content.
    Returns: (metadata_dict, body_text)
    """
    if not content.startswith("---"):
        return {}, content
        
    lines = content.splitlines()
    end_idx = None
    
    # robustly find the second '---'
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
            
    if end_idx is None:
        return {}, content
        
    frontmatter_lines = lines[1:end_idx]
    body = "\n".join(lines[end_idx + 1:]).strip()
    
    # 1. Try standard YAML parsing first for full metadata
    frontmatter_text = "\n".join(frontmatter_lines)
    metadata = {}
    try:
        parsed = yaml.safe_load(frontmatter_text)
        if isinstance(parsed, dict):
            metadata = parsed
    except Exception:
        # If YAML fails, we'll still try to extract critical fields manually below
        pass
        
    # 2. Robustly extract tags/aliases specifically (overriding/augmenting YAML)
    # This handles edge cases where YAML might fail or keys are messy
    tags, aliases = _extract_frontmatter_fields(frontmatter_lines)
    
    # Merge/Normalize tags
    meta_tags = metadata.get("tags", [])
    if isinstance(meta_tags, str):
        meta_tags = [meta_tags]
    if isinstance(meta_tags, list):
        tags.extend([str(t) for t in meta_tags])
    metadata["tags"] = _dedupe_keep_order(tags)
    
    # Merge/Normalize aliases
    meta_aliases = metadata.get("aliases", [])
    if isinstance(meta_aliases, str):
        meta_aliases = [meta_aliases]
    if isinstance(meta_aliases, list):
        aliases.extend([str(a) for a in meta_aliases])
    metadata["aliases"] = _dedupe_keep_order(aliases)
    
    return metadata, body

def sanitize_content(content: str) -> str:
    """Normalize and sanitize raw file content before parsing."""
    if not content:
        return ""
    content = content.replace("\ufeff", "")
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    content = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", content)
    
    # Remove Obsidian comments %% ... %%
    content = re.sub(r'%%.*?%%', '', content, flags=re.DOTALL)
    
    # Remove block references ^blockid at end of lines
    content = re.sub(r'\s\^[a-zA-Z0-9-]+$', '', content, flags=re.MULTILINE)

    # Remove fenced code blocks (including mermaid) from extraction text.
    # content = re.sub(r"```[\s\S]*?```", "", content)  <-- Optional: kept in specific services if needed

    return content
