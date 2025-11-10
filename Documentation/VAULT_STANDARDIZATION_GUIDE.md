# Vault Standardization Implementation Guide

Complete guide for using the vault standardization scripts to review and standardize your Obsidian vault.

## Overview

The vault standardization system helps you:
1. **Standardize note format** using MoC template for MoCs and New Note template for regular notes
2. **Add relevant tags** to each note using knowledge graph and semantic search
3. **Organize notes** into appropriate folders based on content analysis

## Prerequisites

- Python virtual environment activated (`source venv/bin/activate`)
- Required dependencies installed (`pip install -r requirements.txt`)
- Obsidian vault path accessible
- (Optional) Knowledge graph file: `graph_data/knowledge_graph_full.pkl`
- (Optional) ChromaDB directory: `./chroma_db`

## Workflow Overview

```
1. Backup Vault
   ↓
2. Analyze Vault
   ↓
3. Identify MoCs
   ↓
4. Generate Tag Suggestions
   ↓
5. Classify Folders
   ↓
6. Preview Changes (Dry-Run)
   ↓
7. Apply Templates
   ↓
8. Apply Tags
   ↓
9. Move Notes
   ↓
10. Validate Changes
   ↓
11. Generate Reports
```

## Script Reference

### 1. vault_analyzer.py

**Purpose:** Analyze current vault state and generate analysis report.

**Usage:**
```bash
python Scripts/vault_analyzer.py [OPTIONS]
```

**Options:**
- `--vault-path PATH` - Path to Obsidian vault (default: `/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel`)
- `--output PATH` - Output path for analysis report (default: `Documentation/vault_analysis_report.json`)

**Output:**
- JSON report with vault statistics
- Identifies which notes need template updates
- Shows MoC vs regular note breakdown

**Example:**
```bash
python Scripts/vault_analyzer.py --output Documentation/vault_analysis_report.json
```

---

### 2. identify_mocs.py

**Purpose:** Distinguish MoC notes from regular notes.

**Usage:**
```bash
python Scripts/identify_mocs.py [OPTIONS]
```

**Options:**
- `--vault-path PATH` - Path to Obsidian vault
- `--output-dir DIR` - Output directory for JSON lists (default: `.`)

**Output:**
- `moc_list.json` - List of all MoC notes
- `regular_notes_list.json` - List of all regular notes

**Example:**
```bash
python Scripts/identify_mocs.py --vault-path "/path/to/vault" --output-dir .
```

---

### 3. apply_moc_template.py

**Purpose:** Apply MoC template to MoC notes.

**Usage:**
```bash
python Scripts/apply_moc_template.py [OPTIONS]
```

**Options:**
- `--moc-list PATH` - Path to MoC list JSON file (default: `moc_list.json`)
- `--vault-path PATH` - Path to Obsidian vault
- `--template PATH` - Path to MoC template file (default: `Templates/MoC Template.md`)
- `--execute` - Execute changes (default is dry-run)
- `--output PATH` - Output path for results JSON

**Dry-Run Mode (Default):**
- Shows what would be updated
- Displays previews of changes
- Does not modify files

**Execute Mode:**
- Creates `.backup` files before modifying
- Actually updates the files
- Reports what was changed

**Example (Dry-Run):**
```bash
python Scripts/apply_moc_template.py --moc-list moc_list.json
```

**Example (Execute):**
```bash
python Scripts/apply_moc_template.py --moc-list moc_list.json --execute --output moc_template_results.json
```

---

### 4. apply_new_note_template.py

**Purpose:** Apply New Note template to regular notes.

**Usage:**
```bash
python Scripts/apply_new_note_template.py [OPTIONS]
```

**Options:**
- `--regular-notes-list PATH` - Path to regular notes list JSON file (default: `regular_notes_list.json`)
- `--vault-path PATH` - Path to Obsidian vault
- `--template PATH` - Path to New Note template file (default: `Templates/New Note Template.md`)
- `--execute` - Execute changes (default is dry-run)
- `--output PATH` - Output path for results JSON

**Example (Dry-Run):**
```bash
python Scripts/apply_new_note_template.py --regular-notes-list regular_notes_list.json
```

**Example (Execute):**
```bash
python Scripts/apply_new_note_template.py --regular-notes-list regular_notes_list.json --execute --output new_note_template_results.json
```

---

### 5. generate_tags.py

**Purpose:** Generate tag suggestions using knowledge graph, semantic search, and content analysis.

**Usage:**
```bash
python Scripts/generate_tags.py [OPTIONS]
```

**Options:**
- `--notes-list PATH` - Path to notes list JSON file (required)
- `--vault-path PATH` - Path to Obsidian vault
- `--graph-path PATH` - Path to knowledge graph pickle file (optional)
- `--chroma-db-path PATH` - Path to ChromaDB directory (default: `./chroma_db`)
- `--output PATH` - Output path for tag suggestions JSON (default: `tag_suggestions.json`)

**Example:**
```bash
python Scripts/generate_tags.py \
  --notes-list regular_notes_list.json \
  --graph-path graph_data/knowledge_graph_full.pkl \
  --chroma-db-path ./chroma_db \
  --output tag_suggestions.json
```

**Note:** This script uses:
- Knowledge graph entities for tag suggestions
- Similar notes from ChromaDB for tag patterns
- Content analysis for domain and type tags

---

### 6. apply_tags.py

**Purpose:** Apply tags to notes from suggestions.

**Usage:**
```bash
python Scripts/apply_tags.py [OPTIONS]
```

**Options:**
- `--tag-suggestions PATH` - Path to tag suggestions JSON file (default: `tag_suggestions.json`)
- `--vault-path PATH` - Path to Obsidian vault
- `--execute` - Execute changes (default is dry-run)
- `--output PATH` - Output path for results JSON

**Example (Dry-Run):**
```bash
python Scripts/apply_tags.py --tag-suggestions tag_suggestions.json
```

**Example (Execute):**
```bash
python Scripts/apply_tags.py --tag-suggestions tag_suggestions.json --execute --output tag_application_results.json
```

---

### 7. classify_folders.py

**Purpose:** Suggest appropriate folders for notes based on content analysis.

**Usage:**
```bash
python Scripts/classify_folders.py [OPTIONS]
```

**Options:**
- `--notes-list PATH` - Path to notes list JSON file (required)
- `--vault-path PATH` - Path to Obsidian vault
- `--graph-path PATH` - Path to knowledge graph pickle file (optional)
- `--chroma-db-path PATH` - Path to ChromaDB directory (default: `./chroma_db`)
- `--output PATH` - Output path for folder suggestions JSON (default: `folder_suggestions.json`)

**Example:**
```bash
python Scripts/classify_folders.py \
  --notes-list regular_notes_list.json \
  --graph-path graph_data/knowledge_graph_full.pkl \
  --chroma-db-path ./chroma_db \
  --output folder_suggestions.json
```

---

### 8. move_notes_safe.py

**Purpose:** Move notes to suggested folders while updating all internal links.

**Usage:**
```bash
python Scripts/move_notes_safe.py [OPTIONS]
```

**Options:**
- `--folder-suggestions PATH` - Path to folder suggestions JSON file (default: `folder_suggestions.json`)
- `--vault-path PATH` - Path to Obsidian vault
- `--execute` - Execute moves (default is dry-run)
- `--output PATH` - Output path for results JSON

**Features:**
- Updates all internal links (`[[Note Name]]`) in moved files
- Updates all references to moved files in other notes
- Creates `link_updates.json` log

**Example (Dry-Run):**
```bash
python Scripts/move_notes_safe.py --folder-suggestions folder_suggestions.json
```

**Example (Execute):**
```bash
python Scripts/move_notes_safe.py --folder-suggestions folder_suggestions.json --execute --output move_results.json
```

---

### 9. backup_vault.py

**Purpose:** Create timestamped backup of entire vault before making changes.

**Usage:**
```bash
python Scripts/backup_vault.py [OPTIONS]
```

**Options:**
- `--vault-path PATH` - Path to Obsidian vault
- `--backup-dir DIR` - Directory to store backup (default: `.`)
- `--output PATH` - Output path for backup info JSON

**Output:**
- Creates `vault_backup_YYYYMMDD_HHMMSS/` directory
- Includes all markdown files
- Preserves folder structure
- Creates `backup_manifest.json`

**Example:**
```bash
python Scripts/backup_vault.py \
  --vault-path "/path/to/vault" \
  --backup-dir ./backups \
  --output backup_info.json
```

---

### 10. validate_changes.py

**Purpose:** Verify template structure, tags, links, and file accessibility after changes.

**Usage:**
```bash
python Scripts/validate_changes.py [OPTIONS]
```

**Options:**
- `--notes-list PATH` - Path to notes list JSON file (required)
- `--vault-path PATH` - Path to Obsidian vault
- `--is-moc-list` - Treat all notes in list as MoCs
- `--output PATH` - Output path for validation results JSON

**Validates:**
- Template structure (MoC or New Note format)
- Tags (format, duplicates, empty tags)
- Internal links (broken links)
- File accessibility

**Example:**
```bash
python Scripts/validate_changes.py \
  --notes-list regular_notes_list.json \
  --vault-path "/path/to/vault" \
  --output validation_results.json
```

---

### 11. rollback_changes.py

**Purpose:** Restore vault from backup and revert all changes.

**Usage:**
```bash
python Scripts/rollback_changes.py [OPTIONS]
```

**Options:**
- `--backup-path PATH` - Path to backup directory (required)
- `--vault-path PATH` - Path to Obsidian vault
- `--execute` - Execute rollback (default is dry-run)
- `--output PATH` - Output path for rollback results JSON

**Example (Dry-Run):**
```bash
python Scripts/rollback_changes.py --backup-path ./vault_backup_20250109_120000
```

**Example (Execute):**
```bash
python Scripts/rollback_changes.py \
  --backup-path ./vault_backup_20250109_120000 \
  --execute \
  --output rollback_results.json
```

---

### 12. generate_reports.py

**Purpose:** Produce comprehensive reports of all changes made during standardization.

**Usage:**
```bash
python Scripts/generate_reports.py [OPTIONS]
```

**Options:**
- `--analysis-report PATH` - Path to vault analysis report JSON
- `--moc-template-results PATH` - Path to MoC template application results JSON
- `--new-note-template-results PATH` - Path to New Note template application results JSON
- `--tag-results PATH` - Path to tag application results JSON
- `--folder-results PATH` - Path to folder classification results JSON
- `--move-results PATH` - Path to file move results JSON
- `--validation-results PATH` - Path to validation results JSON
- `--link-updates PATH` - Path to link updates JSON
- `--output-dir DIR` - Output directory for reports (default: `Documentation`)

**Output:**
- `Documentation/vault_standardization_report.md` - Summary report
- `Documentation/template_application_log.json` - Detailed template log
- `Documentation/tag_application_log.json` - Tag changes log
- `Documentation/folder_organization_log.json` - Folder moves log
- `Documentation/link_updates_log.json` - Link changes log

**Example:**
```bash
python Scripts/generate_reports.py \
  --analysis-report Documentation/vault_analysis_report.json \
  --moc-template-results moc_template_results.json \
  --new-note-template-results new_note_template_results.json \
  --tag-results tag_application_results.json \
  --folder-results folder_suggestions.json \
  --move-results move_results.json \
  --validation-results validation_results.json \
  --link-updates link_updates.json
```

---

## Complete Workflow Example

### Step 1: Backup Vault
```bash
python Scripts/backup_vault.py \
  --vault-path "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel" \
  --backup-dir ./backups
```

### Step 2: Analyze Vault
```bash
python Scripts/vault_analyzer.py \
  --vault-path "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel" \
  --output Documentation/vault_analysis_report.json
```

### Step 3: Identify MoCs
```bash
python Scripts/identify_mocs.py \
  --vault-path "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
```

### Step 4: Generate Tag Suggestions
```bash
# For MoCs
python Scripts/generate_tags.py \
  --notes-list moc_list.json \
  --vault-path "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel" \
  --graph-path graph_data/knowledge_graph_full.pkl \
  --output moc_tag_suggestions.json

# For regular notes
python Scripts/generate_tags.py \
  --notes-list regular_notes_list.json \
  --vault-path "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel" \
  --graph-path graph_data/knowledge_graph_full.pkl \
  --output regular_tag_suggestions.json
```

### Step 5: Classify Folders
```bash
python Scripts/classify_folders.py \
  --notes-list regular_notes_list.json \
  --vault-path "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel" \
  --graph-path graph_data/knowledge_graph_full.pkl \
  --output folder_suggestions.json
```

### Step 6: Preview Changes (Dry-Run)
```bash
# Preview MoC template application
python Scripts/apply_moc_template.py --moc-list moc_list.json

# Preview New Note template application
python Scripts/apply_new_note_template.py --regular-notes-list regular_notes_list.json

# Preview tag application
python Scripts/apply_tags.py --tag-suggestions regular_tag_suggestions.json

# Preview folder moves
python Scripts/move_notes_safe.py --folder-suggestions folder_suggestions.json
```

### Step 7: Apply Changes (Execute)
```bash
# Apply MoC templates
python Scripts/apply_moc_template.py --moc-list moc_list.json --execute --output moc_template_results.json

# Apply New Note templates
python Scripts/apply_new_note_template.py --regular-notes-list regular_notes_list.json --execute --output new_note_template_results.json

# Apply tags
python Scripts/apply_tags.py --tag-suggestions regular_tag_suggestions.json --execute --output tag_application_results.json

# Move notes
python Scripts/move_notes_safe.py --folder-suggestions folder_suggestions.json --execute --output move_results.json
```

### Step 8: Validate Changes
```bash
python Scripts/validate_changes.py \
  --notes-list regular_notes_list.json \
  --vault-path "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel" \
  --output validation_results.json
```

### Step 9: Generate Reports
```bash
python Scripts/generate_reports.py \
  --analysis-report Documentation/vault_analysis_report.json \
  --moc-template-results moc_template_results.json \
  --new-note-template-results new_note_template_results.json \
  --tag-results tag_application_results.json \
  --folder-results folder_suggestions.json \
  --move-results move_results.json \
  --validation-results validation_results.json \
  --link-updates link_updates.json
```

---

## Incremental Execution

Process in batches for large vaults:

```bash
# Process first 100 notes
python Scripts/apply_new_note_template.py \
  --regular-notes-list regular_notes_list.json \
  --execute \
  --batch-size 100 \
  --batch-number 1
```

---

## Troubleshooting

### Script Fails with "str object has no attribute 'get'"
- **Cause:** YAML frontmatter parsed to non-dict type
- **Fix:** Already fixed in latest version - ensure you have the latest scripts

### JSON Serialization Errors
- **Cause:** Date objects or other non-serializable types in frontmatter
- **Fix:** Scripts now handle this automatically with `default=str`

### Broken Links After Moving Notes
- **Cause:** Link updates may have failed
- **Fix:** Check `link_updates.json` and manually fix if needed, or use rollback

### Template Not Applied Correctly
- **Cause:** Note structure doesn't match expected format
- **Fix:** Review the note manually and adjust template application logic if needed

---

## Configuration Files

### config/vault_paths.json
Default paths for vault and templates.

### config/tag_rules.json
Tag generation rules and keywords.

### config/folder_rules.json
Folder classification rules and mappings.

---

## Safety Features

1. **Dry-Run by Default:** All modification scripts default to dry-run mode
2. **Backup Creation:** `apply_moc_template.py` and `apply_new_note_template.py` create `.backup` files
3. **Link Preservation:** `move_notes_safe.py` updates all internal links automatically
4. **Validation:** `validate_changes.py` checks everything after changes
5. **Rollback:** `rollback_changes.py` can restore from backup

---

## Best Practices

1. **Always backup first** using `backup_vault.py`
2. **Review dry-run results** before executing
3. **Process in batches** for large vaults
4. **Validate after each batch** using `validate_changes.py`
5. **Generate reports** to track progress
6. **Keep backups** until you're satisfied with results

---

## Quick Reference

| Script | Purpose | Dry-Run | Execute Flag |
|--------|---------|---------|--------------|
| `vault_analyzer.py` | Analyze vault | N/A | N/A |
| `identify_mocs.py` | Identify MoCs | N/A | N/A |
| `apply_moc_template.py` | Apply MoC template | ✅ Default | `--execute` |
| `apply_new_note_template.py` | Apply New Note template | ✅ Default | `--execute` |
| `generate_tags.py` | Generate tag suggestions | N/A | N/A |
| `apply_tags.py` | Apply tags | ✅ Default | `--execute` |
| `classify_folders.py` | Classify folders | N/A | N/A |
| `move_notes_safe.py` | Move notes | ✅ Default | `--execute` |
| `backup_vault.py` | Backup vault | N/A | N/A |
| `validate_changes.py` | Validate changes | N/A | N/A |
| `rollback_changes.py` | Rollback changes | ✅ Default | `--execute` |
| `generate_reports.py` | Generate reports | N/A | N/A |

