#!/usr/bin/env python3
"""
Vault Analyzer - Analyze current vault state and generate analysis report.

Scans all markdown files in the vault and identifies:
- Notes with "MoC" in filename or "MoC" tag → MoC candidates
- Notes matching MoC template structure → Already standardized MoCs
- Notes matching New Note template structure → Already standardized notes
- Notes with frontmatter but wrong format → Need template update
- Notes without frontmatter → Need full template application
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime
import yaml


def parse_frontmatter(content: str) -> tuple[Optional[Dict], str]:
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


def check_moc_template_structure(frontmatter: Optional[Dict], body: str) -> bool:
    """Check if note matches MoC template structure."""
    if not frontmatter:
        return False
    
    # Check for MoC tag
    tags = frontmatter.get('tags', [])
    if isinstance(tags, list):
        has_moc_tag = 'MoC' in [str(tag).lower() for tag in tags]
    else:
        has_moc_tag = False
    
    # Check for MoC content structure
    has_links_section = re.search(r'^##\s+Links', body, re.MULTILINE)
    has_related_mocs = re.search(r'^##\s+Related\s+MoCs', body, re.MULTILINE)
    has_external_resources = re.search(r'^##\s+External\s+Resources', body, re.MULTILINE)
    has_notes_section = re.search(r'^##\s+Notes', body, re.MULTILINE)
    
    return has_moc_tag or (has_links_section and has_related_mocs)


def check_new_note_template_structure(frontmatter: Optional[Dict], body: str) -> bool:
    """Check if note matches New Note template structure."""
    if not frontmatter:
        return False
    
    # Check for required sections
    has_main_idea = re.search(r'^###\s+Main\s+Idea', body, re.MULTILINE)
    has_references = re.search(r'^###\s+References', body, re.MULTILINE)
    has_notes = re.search(r'^###\s+Notes', body, re.MULTILINE)
    has_related_notes = re.search(r'^###\s+Related\s+Notes', body, re.MULTILINE)
    
    return bool(has_main_idea and has_references and has_notes)


def is_moc_candidate(filename: str, frontmatter: Optional[Dict], body: str) -> bool:
    """Determine if note is a MoC candidate."""
    # Check filename
    if 'moc' in filename.lower():
        return True
    
    # Check frontmatter
    if frontmatter:
        tags = frontmatter.get('tags', [])
        if isinstance(tags, list):
            if 'MoC' in [str(tag).lower() for tag in tags]:
                return True
        if frontmatter.get('ContentType') == 'MoC':
            return True
    
    # Check content structure (has many links suggesting index/navigation)
    internal_links = len(re.findall(r'\[\[([^\]]+)\]\]', body))
    if internal_links >= 5:  # MoCs typically have many links
        return True
    
    return False


def analyze_note(file_path: Path, vault_root: Path) -> Dict:
    """Analyze a single note file."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'error': str(e),
            'status': 'error'
        }
    
    frontmatter, body = parse_frontmatter(content)
    relative_path = str(file_path.relative_to(vault_root))
    filename = file_path.name
    
    # Determine note type
    is_moc = is_moc_candidate(filename, frontmatter, body)
    has_moc_template = check_moc_template_structure(frontmatter, body) if frontmatter else False
    has_new_note_template = check_new_note_template_structure(frontmatter, body) if frontmatter else False
    
    # Determine status
    if is_moc:
        if has_moc_template:
            status = 'moc_standardized'
        elif frontmatter:
            status = 'moc_needs_template'
        else:
            status = 'moc_needs_full_template'
    else:
        if has_new_note_template:
            status = 'note_standardized'
        elif frontmatter:
            status = 'note_needs_template'
        else:
            status = 'note_needs_full_template'
    
    # Extract metadata
    tags = []
    if frontmatter:
        tags_raw = frontmatter.get('tags', [])
        if isinstance(tags_raw, list):
            tags = [str(tag) for tag in tags_raw]
        elif tags_raw:
            tags = [str(tags_raw)]
    
    aliases = []
    if frontmatter:
        aliases_raw = frontmatter.get('aliases', [])
        if isinstance(aliases_raw, list):
            aliases = [str(alias) for alias in aliases_raw]
        elif aliases_raw:
            aliases = [str(aliases_raw)]
    
    created = frontmatter.get('created', None) if frontmatter else None
    # Convert date objects to strings for JSON serialization
    if created and not isinstance(created, str):
        if hasattr(created, 'isoformat'):
            created = created.isoformat()
        else:
            created = str(created)
    
    # Count internal links
    internal_links = len(re.findall(r'\[\[([^\]]+)\]\]', body))
    
    return {
        'file': relative_path,
        'filename': filename,
        'status': status,
        'is_moc': is_moc,
        'has_frontmatter': frontmatter is not None,
        'has_moc_template': has_moc_template,
        'has_new_note_template': has_new_note_template,
        'tags': tags,
        'aliases': aliases,
        'created': created,
        'internal_links_count': internal_links,
        'file_size': len(content),
        'line_count': len(content.splitlines())
    }


def analyze_vault(vault_path: str, output_path: Optional[str] = None) -> Dict:
    """Analyze entire vault and generate report."""
    vault_root = Path(vault_path)
    if not vault_root.exists():
        raise ValueError(f"Vault path does not exist: {vault_path}")
    
    print(f"Analyzing vault: {vault_path}")
    print("Scanning markdown files...")
    
    # Find all markdown files
    md_files = list(vault_root.rglob("*.md"))
    print(f"Found {len(md_files)} markdown files")
    
    # Analyze each file
    results = []
    status_counts = {
        'moc_standardized': 0,
        'moc_needs_template': 0,
        'moc_needs_full_template': 0,
        'note_standardized': 0,
        'note_needs_template': 0,
        'note_needs_full_template': 0,
        'error': 0
    }
    
    for i, file_path in enumerate(md_files, 1):
        if i % 100 == 0:
            print(f"  Processed {i}/{len(md_files)} files...")
        
        result = analyze_note(file_path, vault_root)
        results.append(result)
        status = result.get('status', 'unknown')
        if status in status_counts:
            status_counts[status] += 1
    
    # Generate summary
    total_files = len(results)
    moc_files = sum(1 for r in results if r.get('is_moc', False))
    regular_files = total_files - moc_files
    
    summary = {
        'analysis_date': datetime.now().isoformat(),
        'vault_path': str(vault_path),
        'total_files': total_files,
        'moc_files': moc_files,
        'regular_files': regular_files,
        'status_breakdown': status_counts,
        'files_with_frontmatter': sum(1 for r in results if r.get('has_frontmatter', False)),
        'files_without_frontmatter': sum(1 for r in results if not r.get('has_frontmatter', False)),
        'standardized_mocs': status_counts['moc_standardized'],
        'standardized_notes': status_counts['note_standardized'],
        'needs_template_update': status_counts['moc_needs_template'] + status_counts['note_needs_template'],
        'needs_full_template': status_counts['moc_needs_full_template'] + status_counts['note_needs_full_template']
    }
    
    report = {
        'summary': summary,
        'files': results
    }
    
    # Save report
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            print(f"\nReport saved to: {output_path}")
        except TypeError as e:
            # If there's still a serialization error, try to find and fix it
            print(f"JSON serialization error: {e}", file=sys.stderr)
            # Convert all non-serializable objects to strings
            def make_serializable(obj):
                if isinstance(obj, dict):
                    return {k: make_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [make_serializable(item) for item in obj]
                elif hasattr(obj, '__dict__'):
                    return str(obj)
                else:
                    return obj
            report_serializable = make_serializable(report)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report_serializable, f, indent=2, ensure_ascii=False, default=str)
            print(f"Report saved (with conversions): {output_path}")
    
    # Print summary
    print("\n" + "="*70)
    print("VAULT ANALYSIS SUMMARY")
    print("="*70)
    print(f"Total files: {total_files}")
    print(f"MoC files: {moc_files}")
    print(f"Regular files: {regular_files}")
    print(f"\nFiles with frontmatter: {summary['files_with_frontmatter']}")
    print(f"Files without frontmatter: {summary['files_without_frontmatter']}")
    print(f"\nAlready standardized:")
    print(f"  MoCs: {status_counts['moc_standardized']}")
    print(f"  Notes: {status_counts['note_standardized']}")
    print(f"\nNeeds template update:")
    print(f"  MoCs: {status_counts['moc_needs_template']}")
    print(f"  Notes: {status_counts['note_needs_template']}")
    print(f"\nNeeds full template:")
    print(f"  MoCs: {status_counts['moc_needs_full_template']}")
    print(f"  Notes: {status_counts['note_needs_full_template']}")
    print(f"\nErrors: {status_counts['error']}")
    print("="*70)
    
    return report


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze Obsidian vault structure')
    parser.add_argument(
        '--vault-path',
        type=str,
        default=os.getenv('OBSIDIAN_VAULT_PATH', '/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel'),
        help='Path to Obsidian vault'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='Documentation/vault_analysis_report.json',
        help='Output path for analysis report'
    )
    
    args = parser.parse_args()
    
    try:
        report = analyze_vault(args.vault_path, args.output)
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

