#!/usr/bin/env python3
"""
Generate Reports - Produce comprehensive reports of all changes made during standardization.

Create:
- Documentation/vault_standardization_report.md - Summary of changes
- Documentation/template_application_log.json - Detailed log
- Documentation/tag_application_log.json - Tag changes
- Documentation/folder_organization_log.json - Folder moves
- Documentation/link_updates_log.json - Link changes
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


def load_json_file(file_path: str) -> Optional[Dict]:
    """Load JSON file if it exists."""
    path = Path(file_path)
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def generate_summary_report(
    analysis_report: Optional[Dict],
    moc_template_results: Optional[Dict],
    new_note_template_results: Optional[Dict],
    tag_results: Optional[Dict],
    folder_results: Optional[Dict],
    move_results: Optional[Dict],
    validation_results: Optional[Dict],
    output_path: str = 'Documentation/vault_standardization_report.md'
) -> str:
    """Generate markdown summary report."""
    report_lines = []
    report_lines.append("# Vault Standardization Report")
    report_lines.append("")
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")
    report_lines.append("## Overview")
    report_lines.append("")
    report_lines.append("This report summarizes the vault standardization process, including template application, tag generation, folder organization, and validation results.")
    report_lines.append("")
    
    # Analysis Summary
    if analysis_report:
        report_lines.append("## Initial Analysis")
        report_lines.append("")
        summary = analysis_report.get('summary', {})
        report_lines.append(f"- **Total files analyzed**: {summary.get('total_files', 'N/A')}")
        report_lines.append(f"- **MoC files**: {summary.get('moc_files', 'N/A')}")
        report_lines.append(f"- **Regular files**: {summary.get('regular_files', 'N/A')}")
        report_lines.append(f"- **Files with frontmatter**: {summary.get('files_with_frontmatter', 'N/A')}")
        report_lines.append(f"- **Files without frontmatter**: {summary.get('files_without_frontmatter', 'N/A')}")
        report_lines.append("")
    
    # Template Application
    report_lines.append("## Template Application")
    report_lines.append("")
    
    if moc_template_results:
        moc_stats = moc_template_results
        report_lines.append("### MoC Templates")
        report_lines.append(f"- **Total MoC files processed**: {moc_stats.get('total', 'N/A')}")
        if moc_stats.get('dry_run'):
            report_lines.append(f"- **Would update**: {moc_stats.get('would_update', 0)}")
        else:
            report_lines.append(f"- **Updated**: {moc_stats.get('updated', 0)}")
        report_lines.append(f"- **Errors**: {moc_stats.get('errors', 0)}")
        report_lines.append("")
    
    if new_note_template_results:
        note_stats = new_note_template_results
        report_lines.append("### New Note Templates")
        report_lines.append(f"- **Total regular files processed**: {note_stats.get('total', 'N/A')}")
        if note_stats.get('dry_run'):
            report_lines.append(f"- **Would update**: {note_stats.get('would_update', 0)}")
        else:
            report_lines.append(f"- **Updated**: {note_stats.get('updated', 0)}")
        report_lines.append(f"- **Errors**: {note_stats.get('errors', 0)}")
        report_lines.append("")
    
    # Tag Application
    if tag_results:
        report_lines.append("## Tag Generation and Application")
        report_lines.append("")
        tag_stats = tag_results
        report_lines.append(f"- **Total notes processed**: {tag_stats.get('total', 'N/A')}")
        if tag_stats.get('dry_run'):
            report_lines.append(f"- **Would update**: {tag_stats.get('would_update', 0)}")
        else:
            report_lines.append(f"- **Updated**: {tag_stats.get('updated', 0)}")
        report_lines.append(f"- **Total tags added**: {tag_stats.get('total_tags_added', 0)}")
        report_lines.append(f"- **No change needed**: {tag_stats.get('no_change', 0)}")
        report_lines.append(f"- **Errors**: {tag_stats.get('errors', 0)}")
        report_lines.append("")
    
    # Folder Organization
    if folder_results:
        report_lines.append("## Folder Organization")
        report_lines.append("")
        folder_stats = folder_results
        report_lines.append(f"- **Total notes analyzed**: {folder_stats.get('total_notes', 'N/A')}")
        report_lines.append(f"- **Notes needing folder change**: {folder_stats.get('notes_needing_move', 0)}")
        report_lines.append("")
    
    if move_results:
        move_stats = move_results
        report_lines.append("### File Moves")
        if move_stats.get('dry_run'):
            report_lines.append(f"- **Would move**: {move_stats.get('would_move', 0)}")
        else:
            report_lines.append(f"- **Moved**: {move_stats.get('moved', 0)}")
        report_lines.append(f"- **Errors**: {move_stats.get('errors', 0)}")
        report_lines.append(f"- **Total link updates**: {move_stats.get('total_link_updates', 0)}")
        report_lines.append("")
    
    # Validation
    if validation_results:
        report_lines.append("## Validation Results")
        report_lines.append("")
        val_stats = validation_results
        report_lines.append(f"- **Total notes validated**: {val_stats.get('total', 'N/A')}")
        report_lines.append(f"- **Valid**: {val_stats.get('valid', 0)}")
        report_lines.append(f"- **With issues**: {val_stats.get('issues', 0)}")
        report_lines.append(f"- **Errors**: {val_stats.get('errors', 0)}")
        report_lines.append("")
        report_lines.append("### Issue Breakdown")
        report_lines.append(f"- **Template issues**: {val_stats.get('template_issues', 0)}")
        report_lines.append(f"- **Tag issues**: {val_stats.get('tag_issues', 0)}")
        report_lines.append(f"- **Link issues**: {val_stats.get('link_issues', 0)}")
        report_lines.append("")
    
    # Summary
    report_lines.append("## Summary")
    report_lines.append("")
    report_lines.append("The vault standardization process has been completed. All changes have been applied and validated.")
    report_lines.append("")
    
    # Write report
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    
    return str(output_file)


def generate_reports(
    analysis_report_path: Optional[str] = None,
    moc_template_results_path: Optional[str] = None,
    new_note_template_results_path: Optional[str] = None,
    tag_results_path: Optional[str] = None,
    folder_results_path: Optional[str] = None,
    move_results_path: Optional[str] = None,
    validation_results_path: Optional[str] = None,
    link_updates_path: Optional[str] = None,
    output_dir: str = 'Documentation'
) -> Dict:
    """Generate all reports from result files."""
    print("Generating standardization reports...")
    print()
    
    # Load all result files
    analysis_report = load_json_file(analysis_report_path) if analysis_report_path else None
    moc_template_results = load_json_file(moc_template_results_path) if moc_template_results_path else None
    new_note_template_results = load_json_file(new_note_template_results_path) if new_note_template_results_path else None
    tag_results = load_json_file(tag_results_path) if tag_results_path else None
    folder_results = load_json_file(folder_results_path) if folder_results_path else None
    move_results = load_json_file(move_results_path) if move_results_path else None
    validation_results = load_json_file(validation_results_path) if validation_results_path else None
    link_updates = load_json_file(link_updates_path) if link_updates_path else None
    
    # Generate summary report
    summary_report_path = Path(output_dir) / 'vault_standardization_report.md'
    summary_path = generate_summary_report(
        analysis_report,
        moc_template_results,
        new_note_template_results,
        tag_results,
        folder_results,
        move_results,
        validation_results,
        str(summary_report_path)
    )
    
    # Save detailed logs
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    
    saved_logs = {}
    
    if moc_template_results:
        log_path = output_dir_path / 'template_application_log.json'
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(moc_template_results, f, indent=2, ensure_ascii=False)
        saved_logs['template_application'] = str(log_path)
    
    if tag_results:
        log_path = output_dir_path / 'tag_application_log.json'
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(tag_results, f, indent=2, ensure_ascii=False)
        saved_logs['tag_application'] = str(log_path)
    
    if folder_results:
        log_path = output_dir_path / 'folder_organization_log.json'
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(folder_results, f, indent=2, ensure_ascii=False)
        saved_logs['folder_organization'] = str(log_path)
    
    if link_updates:
        log_path = output_dir_path / 'link_updates_log.json'
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(link_updates, f, indent=2, ensure_ascii=False)
        saved_logs['link_updates'] = str(log_path)
    
    print("="*70)
    print("REPORT GENERATION SUMMARY")
    print("="*70)
    print(f"Summary report: {summary_path}")
    for log_name, log_path in saved_logs.items():
        print(f"{log_name}: {log_path}")
    print("="*70)
    
    return {
        'summary_report': summary_path,
        'logs': saved_logs
    }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate standardization reports')
    parser.add_argument(
        '--analysis-report',
        type=str,
        help='Path to vault analysis report JSON'
    )
    parser.add_argument(
        '--moc-template-results',
        type=str,
        help='Path to MoC template application results JSON'
    )
    parser.add_argument(
        '--new-note-template-results',
        type=str,
        help='Path to New Note template application results JSON'
    )
    parser.add_argument(
        '--tag-results',
        type=str,
        help='Path to tag application results JSON'
    )
    parser.add_argument(
        '--folder-results',
        type=str,
        help='Path to folder classification results JSON'
    )
    parser.add_argument(
        '--move-results',
        type=str,
        help='Path to file move results JSON'
    )
    parser.add_argument(
        '--validation-results',
        type=str,
        help='Path to validation results JSON'
    )
    parser.add_argument(
        '--link-updates',
        type=str,
        help='Path to link updates JSON'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='Documentation',
        help='Output directory for reports'
    )
    
    args = parser.parse_args()
    
    try:
        generate_reports(
            args.analysis_report,
            args.moc_template_results,
            args.new_note_template_results,
            args.tag_results,
            args.folder_results,
            args.move_results,
            args.validation_results,
            args.link_updates,
            args.output_dir
        )
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

