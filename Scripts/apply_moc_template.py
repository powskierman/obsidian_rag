#!/usr/bin/env python3
"""
Apply MoC Template - Standardize MoC notes using MoC Template.md structure.

For each MoC note:
- Read current content
- Extract existing metadata (tags, aliases, created date)
- Apply MoC template structure while preserving existing content
- Dry-run mode by default
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import yaml
import shutil


def parse_frontmatter(content: str) -> tuple[Dict | None, str]:
    """Extract frontmatter from markdown content."""
    frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(frontmatter_pattern, content, re.DOTALL)
    
    if not match:
        return None, content
    
    frontmatter_text = match.group(1)
    body = match.group(2)
    
    try:
        frontmatter = yaml.safe_load(frontmatter_text)
        # Ensure frontmatter is a dict, not a string or other type
        if frontmatter is None:
            frontmatter = {}
        elif not isinstance(frontmatter, dict):
            # If YAML parsed to a non-dict (e.g., string), treat as no frontmatter
            return None, content
        return frontmatter, body
    except yaml.YAMLError:
        return None, content


def extract_links_from_body(body: str) -> Dict[str, List[str]]:
    """Extract different types of links from body."""
    # Internal links - match [[link]] but avoid triple brackets [[[link]]]
    # First, remove any existing Links section to avoid extracting from formatted lists
    body_for_extraction = re.sub(r'^##\s+Links.*?(?=\n##|\Z)', '', body, flags=re.DOTALL | re.MULTILINE)
    
    # Match [[link]] but not when preceded by [ (to avoid [[[link]]])
    # Use a more robust pattern that handles edge cases
    internal_links_raw = []
    # Find all [[...]] patterns
    for match in re.finditer(r'\[\[([^\]]+)\]\]', body_for_extraction):
        # Check if this is not part of a triple bracket [[[...]]]
        start_pos = match.start()
        # Check character before the match
        if start_pos > 0:
            char_before = body_for_extraction[start_pos - 1]
            if char_before == '[':
                # This is part of [[[...]]], skip it
                continue
        # Also check if the match itself contains triple brackets (malformed)
        link_text = match.group(1)
        if link_text.startswith('[') or ']]' in link_text:
            # Malformed link, skip it
            continue
        internal_links_raw.append(link_text)
    
    # Clean and deduplicate links
    # Remove any leading/trailing whitespace and normalize
    internal_links_cleaned = []
    seen = set()
    for link in internal_links_raw:
        link_clean = link.strip()
        # Skip empty links
        if not link_clean:
            continue
        # Normalize to lowercase for deduplication, but keep original case
        link_key = link_clean.lower()
        if link_key not in seen:
            seen.add(link_key)
            internal_links_cleaned.append(link_clean)
    
    # External links (markdown format and plain URLs)
    external_links = re.findall(r'\[([^\]]+)\]\(([^\)]+)\)', body)
    external_urls = []
    seen_urls = set()
    for text, url in external_links:
        if url.startswith('http') and url not in seen_urls:
            seen_urls.add(url)
            external_urls.append(url)
    
    # Also extract plain URLs (lines starting with - followed by http URL)
    plain_url_pattern = r'^-\s*(https?://[^\s]+)'
    plain_urls = re.findall(plain_url_pattern, body, re.MULTILINE)
    for url in plain_urls:
        url = url.strip()
        if url not in seen_urls:
            seen_urls.add(url)
            external_urls.append(url)
    
    # MoC links (notes with "MoC" in name)
    moc_links = []
    seen_mocs = set()
    for link in internal_links_cleaned:
        link_lower = link.lower()
        if 'moc' in link_lower and link_lower not in seen_mocs:
            seen_mocs.add(link_lower)
            moc_links.append(link)
    
    return {
        'internal': internal_links_cleaned,
        'external': external_urls,
        'moc': moc_links
    }


def extract_backlink_from_content(content: str) -> str:
    """Extract backlink section from content."""
    backlink_pattern = r'###?\s+Backlink\s*\n(.*?)(?=\n##|\Z)'
    match = re.search(backlink_pattern, content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ''


def extract_title(file_path: Path, body: str) -> str:
    """Extract title from filename or first heading."""
    # Try to find first H1 heading
    h1_match = re.search(r'^#\s+(.+)$', body, re.MULTILINE)
    if h1_match:
        return h1_match.group(1).strip()
    
    # Fall back to filename without extension
    return file_path.stem


def extract_overview(body: str, title: str, tags: List[str]) -> str:
    """Extract overview text from existing content or generate meaningful one."""
    # Look for existing Overview section
    overview_pattern = r'##\s+Overview\s*\n(.*?)(?=\n##|\Z)'
    match = re.search(overview_pattern, body, re.DOTALL | re.IGNORECASE)
    if match:
        overview_text = match.group(1).strip()
        # Clean up any markdown formatting that shouldn't be there
        overview_text = re.sub(r'^[-*+]\s+', '', overview_text, flags=re.MULTILINE)
        # Remove placeholder text
        if 'this moc connects notes about' in overview_text.lower():
            overview_text = ''  # Will generate better one
        else:
            return overview_text
    
    # Try to extract from first paragraph or description
    # Look for text before first major section
    first_section = re.search(r'^##\s+', body, re.MULTILINE)
    if first_section:
        intro_text = body[:first_section.start()].strip()
        # Remove any headings
        intro_text = re.sub(r'^#+\s+.*$', '', intro_text, flags=re.MULTILINE)
        if intro_text and len(intro_text) > 20:
            return intro_text
    
    # Generate a better overview based on content
    # Look for external resources to understand the topic
    external_urls = re.findall(r'https?://[^\s]+', body)
    
    # Look for key terms in the content
    content_lower = body.lower()
    
    # Build overview based on what we find
    overview_parts = []
    
    # Use title to create overview
    title_clean = title.replace(' MoC', '').replace('MoC', '').strip()
    if title_clean:
        # Create a more natural description
        if external_urls:
            overview_parts.append(f"This MoC organizes notes and resources about {title_clean.lower()}.")
        else:
            overview_parts.append(f"This MoC connects notes about {title_clean.lower()}.")
    
    # Add context from tags if available
    relevant_tags = [t for t in tags if t.lower() not in ['moc', 'map']]
    if relevant_tags and len(relevant_tags) > 0:
        tag_context = ', '.join(relevant_tags[:2])  # Use first 2 relevant tags
        if tag_context:
            overview_parts.append(f"Focus areas include {tag_context}.")
    
    # Add context from external resources
    if external_urls:
        domain_count = len(set(url.split('/')[2] if '/' in url else url for url in external_urls[:3]))
        if domain_count > 0:
            overview_parts.append(f"External resources and tools are documented for reference.")
    
    return ' '.join(overview_parts) if overview_parts else ''


def organize_links_into_components(links: List[str], body: str) -> Dict[str, List[str]]:
    """Organize links into logical component groups based on context."""
    components = {}
    
    # Common component categories (can be expanded)
    categories = {
        'infrastructure': ['setup', 'configuration', 'installation', 'deployment', 'infrastructure'],
        'integration': ['integration', 'api', 'connect', 'bridge', 'interface'],
        'automation': ['automation', 'workflow', 'trigger', 'action', 'rule'],
        'analysis': ['analysis', 'monitor', 'track', 'log', 'metric', 'data'],
        'optimization': ['optimize', 'performance', 'tune', 'improve', 'enhance'],
        'development': ['develop', 'code', 'script', 'component', 'custom'],
    }
    
    # Try to extract existing component sections
    component_pattern = r'###\s+([^\n]+)\s*\n((?:- \[\[[^\]]+\]\]\s*\n?)+)'
    matches = re.finditer(component_pattern, body, re.MULTILINE)
    for match in matches:
        component_name = match.group(1).strip()
        component_links = re.findall(r'\[\[([^\]]+)\]\]', match.group(2))
        if component_links:
            components[component_name] = component_links
    
    # If no existing components found, try to categorize links
    if not components:
        for link in links:
            link_lower = link.lower()
            categorized = False
            for category, keywords in categories.items():
                if any(keyword in link_lower for keyword in keywords):
                    if category not in components:
                        components[category.title()] = []
                    components[category.title()].append(link)
                    categorized = True
                    break
            
            if not categorized:
                # Default category
                if 'General' not in components:
                    components['General'] = []
                components['General'].append(link)
    
    return components


def extract_workflows(body: str) -> List[str]:
    """Extract workflow patterns from content."""
    workflows = []
    
    # Look for existing workflows section
    workflow_pattern = r'##\s+Key\s+Workflows?\s*\n(.*?)(?=\n##|\Z)'
    match = re.search(workflow_pattern, body, re.DOTALL | re.IGNORECASE)
    if match:
        workflow_text = match.group(1)
        # Extract workflow lines (lines with arrows or patterns)
        workflow_lines = re.findall(r'^\*\*[^*]+\*\*.*$', workflow_text, re.MULTILINE)
        workflows.extend([line.strip() for line in workflow_lines if line.strip()])
    
    # Look for arrow patterns (→ or ->)
    # Use separate patterns for each arrow type
    arrow_patterns = [
        r'\[\[([^\]]+)\]\]\s*→\s*\[\[([^\]]+)\]\]',  # Unicode arrow
        r'\[\[([^\]]+)\]\]\s*->\s*\[\[([^\]]+)\]\]',  # ASCII arrow
    ]
    for arrow_pattern in arrow_patterns:
        arrow_matches = re.finditer(arrow_pattern, body)
        for match in arrow_matches:
            workflow = f"**{match.group(1)}** → [[{match.group(2)}]]"
            if workflow not in workflows:
                workflows.append(workflow)
    
    return workflows


def extract_projects(body: str) -> List[Dict[str, str]]:
    """Extract project information from content."""
    projects = []
    
    # Look for existing projects section
    project_pattern = r'##\s+Recent\s+Projects?\s*\n(.*?)(?=\n##|\Z)'
    match = re.search(project_pattern, body, re.DOTALL | re.IGNORECASE)
    if match:
        project_text = match.group(1)
        # Extract project lines with status
        project_lines = re.findall(r'-\s*\[\[([^\]]+)\]\]\s*\(([^)]+)\)', project_text)
        for link, status in project_lines:
            projects.append({'link': link, 'status': status})
    
    return projects


def format_core_components(components: Dict[str, List[str]]) -> str:
    """Format core components section."""
    if not components:
        return ''
    
    lines = []
    for component_name, links in components.items():
        lines.append(f'### {component_name}')
        for link in links:
            lines.append(f'- [[{link}]]')
        lines.append('')
    
    return '\n'.join(lines).strip()


def format_workflows(workflows: List[str]) -> str:
    """Format workflows section."""
    if not workflows:
        return ''
    
    lines = []
    for workflow in workflows:
        lines.append(workflow)
    
    return '\n'.join(lines).strip()


def format_projects(projects: List[Dict[str, str]]) -> str:
    """Format projects section."""
    if not projects:
        return ''
    
    lines = []
    for project in projects:
        lines.append(f"- [[{project['link']}]] ({project['status']})")
    
    return '\n'.join(lines).strip()


def apply_moc_template(file_path: Path, vault_root: Path, template_path: Path, dry_run: bool = True) -> Dict:
    """Apply MoC template to a note file."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'error',
            'error': str(e)
        }
    
    # Read template
    try:
        template_content = template_path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'error',
            'error': f'Failed to read template: {e}'
        }
    
    # Parse existing content
    frontmatter, body = parse_frontmatter(content)
    
    # Extract existing metadata
    existing_aliases = []
    existing_tags = []
    existing_created = None
    existing_backlink = ''
    
    if frontmatter:
        aliases_raw = frontmatter.get('aliases', [])
        if isinstance(aliases_raw, list):
            existing_aliases = [str(a) for a in aliases_raw]
        elif aliases_raw:
            existing_aliases = [str(aliases_raw)]
        
        tags_raw = frontmatter.get('tags', [])
        if isinstance(tags_raw, list):
            existing_tags = [str(t) for t in tags_raw]
        elif tags_raw:
            existing_tags = [str(tags_raw)]
        
        existing_created = frontmatter.get('created')
        existing_backlink_raw = frontmatter.get('Backlink', '')
        
        # Handle backlink - can be string or list
        if isinstance(existing_backlink_raw, list):
            existing_backlink = existing_backlink_raw[0] if existing_backlink_raw else ''
        else:
            existing_backlink = existing_backlink_raw or ''
    
    # Extract backlink from content if not in frontmatter
    if not existing_backlink:
        existing_backlink = extract_backlink_from_content(content)
    
    # Format backlink properly - should be quoted link like "[[Link Name]]"
    if existing_backlink:
        # Ensure it's a string
        if not isinstance(existing_backlink, str):
            existing_backlink = str(existing_backlink)
        # Remove existing quotes if present
        existing_backlink = existing_backlink.strip().strip('"').strip("'")
        # If it's already a link format [[...]], keep it, otherwise try to extract link
        if not existing_backlink.startswith('[['):
            # Try to extract link from the text
            link_match = re.search(r'\[\[([^\]]+)\]\]', existing_backlink)
            if link_match:
                existing_backlink = f"[[{link_match.group(1)}]]"
            # If no link found, use the text as-is
        # Ensure it's in the format [[Link Name]]
        if existing_backlink and not existing_backlink.startswith('[['):
            # If it's not a link, try to make it one
            existing_backlink = f"[[{existing_backlink}]]"
    
    # Ensure MoC tag is present (only once)
    existing_tags_lower = [t.lower() for t in existing_tags]
    if 'moc' not in existing_tags_lower:
        existing_tags.append('MoC')
    # Remove duplicates while preserving order
    seen = set()
    existing_tags = [t for t in existing_tags if not (t.lower() in seen or seen.add(t.lower()))]
    
    # Extract links from body
    links_info = extract_links_from_body(body)
    
    # Build new frontmatter
    new_frontmatter = {
        'aliases': existing_aliases if existing_aliases else None,
        'tags': existing_tags,
        'created': existing_created or datetime.fromtimestamp(file_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
        'Backlink': existing_backlink if existing_backlink else None
    }
    
    # Remove None values
    new_frontmatter = {k: v for k, v in new_frontmatter.items() if v is not None}
    
    # Extract content for new structure
    title = extract_title(file_path, body)
    overview = extract_overview(body, title, existing_tags)
    components = organize_links_into_components(links_info['internal'], body)
    workflows = extract_workflows(body)
    projects = extract_projects(body)
    related_mocs = links_info['moc']
    
    # Build new body with new MoC structure
    new_body_parts = []
    
    # Title
    new_body_parts.append(f'# {title}')
    new_body_parts.append('')
    
    # Overview
    new_body_parts.append('## Overview')
    if overview:
        new_body_parts.append(overview)
    else:
        # Fallback: try to extract descriptive text from content
        first_lines = body.split('\n')[:15]
        descriptive_text = ''
        for line in first_lines:
            line = line.strip()
            # Skip headings, empty lines, list items, and URLs
            if (line and not line.startswith('#') and not line.startswith('-') 
                and not line.startswith('*') and not line.startswith('http')):
                if len(line) > 40:  # Substantial text
                    descriptive_text = line
                    break
        
        if descriptive_text:
            new_body_parts.append(descriptive_text)
        else:
            # Last resort: simple description
            title_clean = title.replace(' MoC', '').replace('MoC', '').strip()
            new_body_parts.append(f'This MoC organizes notes and resources about {title_clean.lower() if title_clean else "this topic"}.')
    new_body_parts.append('')
    
    # Core Components
    if components:
        new_body_parts.append('## Core Components')
        new_body_parts.append('')
        new_body_parts.append(format_core_components(components))
        new_body_parts.append('')
    elif links_info['internal']:
        # If we have links but no components, create a simple list
        new_body_parts.append('## Core Components')
        new_body_parts.append('')
        for link in links_info['internal']:
            new_body_parts.append(f'- [[{link}]]')
        new_body_parts.append('')
    
    # Key Workflows
    if workflows:
        new_body_parts.append('## Key Workflows')
        new_body_parts.append('')
        new_body_parts.append(format_workflows(workflows))
        new_body_parts.append('')
    
    # Recent Projects
    if projects:
        new_body_parts.append('## Recent Projects')
        new_body_parts.append('')
        new_body_parts.append(format_projects(projects))
        new_body_parts.append('')
    
    # Related Maps
    if related_mocs:
        new_body_parts.append('## Related Maps')
        new_body_parts.append('')
        for moc_link in related_mocs:
            new_body_parts.append(f'- [[{moc_link}]]')
        new_body_parts.append('')
    
    # External Resources (preserve from original)
    if links_info['external']:
        new_body_parts.append('## External Resources')
        new_body_parts.append('')
        for url in links_info['external']:
            new_body_parts.append(f'- {url}')
        new_body_parts.append('')
    
    # Status & Notes
    new_body_parts.append('## Status & Notes')
    new_body_parts.append('')
    
    # Extract any remaining content that wasn't captured in structured sections
    # Remove sections we've already extracted
    body_cleaned = body
    sections_to_remove = [
        r'^#\s+.*$',  # Title
        r'^##\s+Overview.*?(?=\n##|\Z)',
        r'^##\s+Core\s+Components.*?(?=\n##|\Z)',
        r'^##\s+Key\s+Workflows?.*?(?=\n##|\Z)',
        r'^##\s+Recent\s+Projects?.*?(?=\n##|\Z)',
        r'^##\s+Related\s+Maps?.*?(?=\n##|\Z)',
        r'^##\s+Status\s+&\s+Notes?.*?(?=\n##|\Z)',
        r'^##\s+Links.*?(?=\n##|\Z)',
        r'^##\s+Related\s+MoCs?.*?(?=\n##|\Z)',
        r'^##\s+External\s+Resources?.*?(?=\n##|\Z)',
        r'^##\s+Notes?\s*\n',
    ]
    
    for pattern in sections_to_remove:
        body_cleaned = re.sub(pattern, '', body_cleaned, flags=re.DOTALL | re.MULTILINE | re.IGNORECASE)
    
    # Add remaining content to Status & Notes if there's anything meaningful
    remaining_content = body_cleaned.strip()
    if remaining_content and len(remaining_content) > 10:
        new_body_parts.append(remaining_content)
        new_body_parts.append('')
    
    # Add last reviewed date
    new_body_parts.append(f'Last reviewed: {datetime.now().strftime("%Y-%m-%d")}')
    
    # Combine
    new_body = '\n'.join(new_body_parts)
    
    # Build new content
    # For Backlink, we need to ensure it's quoted properly in YAML
    # YAML will auto-quote strings with special characters like [[, but we want explicit quotes
    # So we'll handle Backlink specially before dumping
    frontmatter_for_yaml = new_frontmatter.copy()
    backlink_value = None
    if 'Backlink' in frontmatter_for_yaml and frontmatter_for_yaml['Backlink']:
        backlink_value = frontmatter_for_yaml['Backlink']
        # Remove Backlink temporarily to avoid YAML auto-quoting
        del frontmatter_for_yaml['Backlink']
    
    frontmatter_yaml = yaml.dump(frontmatter_for_yaml, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    # Now add Backlink with explicit quotes
    if backlink_value:
        # Remove any existing quotes from the value
        backlink_clean = backlink_value.strip().strip('"').strip("'")
        # Add Backlink line with explicit quotes
        # Find where to insert it (after tags, before or after created)
        # For simplicity, add it after the last line of frontmatter
        frontmatter_yaml = frontmatter_yaml.rstrip() + f'\nBacklink: "{backlink_clean}"\n'
    
    new_content = f"---\n{frontmatter_yaml}---\n{new_body}\n"
    
    # Apply changes
    if not dry_run:
        # Create backup
        backup_path = file_path.with_suffix('.md.backup')
        shutil.copy2(file_path, backup_path)
        
        # Write new content
        file_path.write_text(new_content, encoding='utf-8')
        
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'updated',
            'backup': str(backup_path.relative_to(vault_root))
        }
    else:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'would_update',
            'preview': new_content
        }


def apply_moc_templates(
    moc_list_path: str,
    vault_path: str,
    template_path: str,
    dry_run: bool = True
) -> Dict:
    """Apply MoC template to all MoC notes."""
    vault_root = Path(vault_path)
    template_file = Path(template_path)
    
    if not template_file.exists():
        raise ValueError(f"Template file not found: {template_path}")
    
    # Load MoC list
    with open(moc_list_path, 'r', encoding='utf-8') as f:
        moc_list = json.load(f)
    
    print(f"Applying MoC template to {len(moc_list)} files")
    print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    print()
    
    results = []
    for i, moc_info in enumerate(moc_list, 1):
        file_path = vault_root / moc_info['file']
        if not file_path.exists():
            print(f"  [{i}/{len(moc_list)}] File not found: {moc_info['file']}")
            continue
        
        print(f"  [{i}/{len(moc_list)}] Processing: {moc_info['file']}")
        result = apply_moc_template(file_path, vault_root, template_file, dry_run)
        results.append(result)
    
    # Summary
    updated = sum(1 for r in results if r.get('status') == 'updated')
    would_update = sum(1 for r in results if r.get('status') == 'would_update')
    errors = sum(1 for r in results if r.get('status') == 'error')
    
    print("\n" + "="*70)
    print("MoC TEMPLATE APPLICATION SUMMARY")
    print("="*70)
    if dry_run:
        print(f"Would update: {would_update}")
    else:
        print(f"Updated: {updated}")
    print(f"Errors: {errors}")
    print("="*70)
    
    return {
        'dry_run': dry_run,
        'total': len(results),
        'updated': updated if not dry_run else 0,
        'would_update': would_update if dry_run else 0,
        'errors': errors,
        'results': results
    }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Apply MoC template to MoC notes')
    parser.add_argument(
        '--moc-list',
        type=str,
        default='moc_list.json',
        help='Path to MoC list JSON file'
    )
    parser.add_argument(
        '--vault-path',
        type=str,
        default=os.getenv('OBSIDIAN_VAULT_PATH', '/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel'),
        help='Path to Obsidian vault'
    )
    parser.add_argument(
        '--template',
        type=str,
        default='/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel/Templates/MoC Template.md',
        help='Path to MoC template file'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Execute changes (default is dry-run)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output path for results JSON'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed results for all MoCs'
    )
    parser.add_argument(
        '--show-file',
        type=str,
        help='Show detailed result for a specific file (partial filename match)'
    )
    parser.add_argument(
        '--show-index',
        type=int,
        help='Show detailed result for a specific MoC by index (1-based)'
    )
    
    args = parser.parse_args()
    
    try:
        results = apply_moc_templates(
            args.moc_list,
            args.vault_path,
            args.template,
            dry_run=not args.execute
        )
        
        # Show detailed results if requested
        if args.verbose:
            print("\n" + "="*70)
            print("DETAILED RESULTS FOR ALL MoCs")
            print("="*70)
            for i, result in enumerate(results['results'], 1):
                print(f"\n[{i}] {result.get('file', 'unknown')}")
                print(f"  Status: {result.get('status', 'unknown')}")
                if result.get('error'):
                    print(f"  Error: {result['error']}")
                if result.get('backup'):
                    print(f"  Backup: {result['backup']}")
                if result.get('preview'):
                    print(f"  Preview (first 200 chars):")
                    print(f"    {result['preview'][:200]}...")
        
        elif args.show_file:
            print("\n" + "="*70)
            print(f"SEARCHING FOR: {args.show_file}")
            print("="*70)
            found = False
            for i, result in enumerate(results['results'], 1):
                if args.show_file.lower() in result.get('file', '').lower():
                    found = True
                    print(f"\n[{i}] {result.get('file', 'unknown')}")
                    print(f"  Status: {result.get('status', 'unknown')}")
                    if result.get('error'):
                        print(f"  Error: {result['error']}")
                    if result.get('backup'):
                        print(f"  Backup: {result['backup']}")
                    if result.get('preview'):
                        print(f"\n  Preview:")
                        print("  " + "-"*66)
                        preview_lines = result['preview'].split('\n')[:30]  # First 30 lines
                        for line in preview_lines:
                            print(f"  {line}")
                        if len(result['preview'].split('\n')) > 30:
                            print(f"  ... ({len(result['preview'].split('\n')) - 30} more lines)")
                        print("  " + "-"*66)
            if not found:
                print(f"\nNo MoC found matching: {args.show_file}")
        
        elif args.show_index:
            if 1 <= args.show_index <= len(results['results']):
                result = results['results'][args.show_index - 1]
                print("\n" + "="*70)
                print(f"DETAILED RESULT FOR MoC #{args.show_index}")
                print("="*70)
                print(f"\nFile: {result.get('file', 'unknown')}")
                print(f"Status: {result.get('status', 'unknown')}")
                if result.get('error'):
                    print(f"Error: {result['error']}")
                if result.get('backup'):
                    print(f"Backup: {result['backup']}")
                if result.get('preview'):
                    print(f"\nPreview:")
                    print("-"*70)
                    preview_lines = result['preview'].split('\n')[:50]  # First 50 lines
                    for line in preview_lines:
                        print(line)
                    if len(result['preview'].split('\n')) > 50:
                        print(f"... ({len(result['preview'].split('\n')) - 50} more lines)")
                    print("-"*70)
            else:
                print(f"Error: Index {args.show_index} is out of range (1-{len(results['results'])})")
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\nResults saved to: {args.output}")
        
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

