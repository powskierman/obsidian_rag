---
title: Obsidian Vault Reorganizer - README
aliases: [Vault Reorganizer Package, Reorganizer Overview]
tags: [obsidian, readme, documentation, mcp]
created: 2025-10-25
---

# Obsidian Vault Reorganizer

A comprehensive skill package for systematically reorganizing Obsidian vaults using MCP (Model Context Protocol) tools and Claude AI.

---

## What This Package Includes

This skill package provides everything needed to reorganize an Obsidian vault:

1. **[[Obsidian Vault Reorganizer - Overview]]** - High-level introduction and quick start
2. **[[Obsidian Vault Reorganizer - Complete Workflow]]** - Detailed 5-phase reorganization process
3. **[[Obsidian Vault Reorganizer - Workflow Checklist]]** - Interactive checklist with checkboxes
4. **[[Obsidian Vault Reorganizer - MCP Tools Reference]]** - Complete MCP tools documentation
5. **[[Obsidian Vault Reorganizer - JsonLogic Queries]]** - Complex search patterns and examples
6. **[[Obsidian Vault Reorganizer - Helper Functions]]** - Python utilities and code examples
7. **This README** - Package overview and quick reference

---

## Quick Start

### Prerequisites

1. **Backup your vault** - Always backup before making changes
2. **Obsidian MCP Server** - Must be running and connected
3. **Claude with MCP support** - Access to Obsidian MCP tools
4. **Python (optional)** - For helper functions and automation

### 5-Minute Quick Start

```markdown
1. Read: [[Obsidian Vault Reorganizer - Overview]]
2. Plan: Define your folder structure and frontmatter template
3. Backup: Create full vault backup
4. Execute: Follow [[Obsidian Vault Reorganizer - Workflow Checklist]]
5. Verify: Check vault integrity with final validation
```

### First-Time Setup

1. **Review your vault structure**
   - How many notes do you have?
   - Do you already have folders?
   - What categories/tags exist?

2. **Define your standards**
   - What frontmatter fields do you need?
   - What folder structure makes sense?
   - What naming conventions to use?

3. **Test on a small subset**
   - Create a test vault with 10-20 notes
   - Run through the complete workflow
   - Verify everything works as expected

4. **Run on your real vault**
   - Follow the checklist step by step
   - Take breaks between phases
   - Keep detailed logs

---

## What This Package Does

### The 5 Phases

**Phase 1: Discovery & Analysis**
- Scans vault for statistics and file inventory
- Classifies notes (empty, missing frontmatter, orphaned, well-formed)
- Builds comprehensive analysis report

**Phase 2: Empty Note Cleanup**
- Identifies truly empty or useless notes
- Allows review before deletion
- Safely deletes with logging and confirmation

**Phase 3: Frontmatter Standardization**
- Adds consistent frontmatter to all notes
- Extracts metadata from content (tags, categories)
- Preserves existing frontmatter where appropriate

**Phase 4: Backlink Identification**
- Finds orphaned notes (no incoming links)
- Uses semantic search to find related notes
- Adds appropriate backlinks to frontmatter

**Phase 5: Folder Organization**
- Analyzes note categories and builds folder hierarchy
- Maps notes to appropriate folders
- Moves files and updates wikilinks

---

## Key Features

✅ **Safe Operations**
- Previews all destructive operations
- Requires confirmation for deletions
- Creates detailed operation logs
- Supports rollback procedures

✅ **Smart Analysis**
- Semantic search for related notes
- Automatic category inference
- Key concept extraction
- Broken link detection

✅ **Batch Processing**
- Processes 10-20 files at a time
- Shows progress indicators
- Handles large vaults efficiently
- Resumable operations

✅ **Flexible Configuration**
- Customizable frontmatter templates
- User-defined folder structures
- Adjustable batch sizes
- Optional bidirectional linking

---

## MCP Tools Used

This package leverages the following Obsidian MCP tools:

| Tool | Purpose | Phase Used |
|------|---------|------------|
| `obsidian_vault_stats` | Get vault statistics | 1, 6 |
| `obsidian_list_files_in_vault` | List all files | 1 |
| `obsidian_batch_get_file_contents` | Read multiple files | 1, 3, 4 |
| `obsidian_get_file_contents` | Read single file | 3, 4 |
| `obsidian_delete_file` | Delete files | 2 |
| `obsidian_patch_content` | Add/modify content | 3, 4, 5 |
| `obsidian_simple_search` | Semantic search | 4 |
| `obsidian_complex_search` | JsonLogic queries | 1, 5 |
| `obsidian_graph_query` | Knowledge graph queries | 1, 4, 6 |

For detailed documentation, see [[Obsidian Vault Reorganizer - MCP Tools Reference]]

---

## Document Guide

### For First-Time Users
**Start here →** [[Obsidian Vault Reorganizer - Overview]]
- Quick introduction
- Key concepts
- What to expect

**Then read →** [[Obsidian Vault Reorganizer - Complete Workflow]]
- Detailed phase descriptions
- Step-by-step process
- Safety measures

**Use during execution →** [[Obsidian Vault Reorganizer - Workflow Checklist]]
- Interactive checklist
- Track your progress
- Verify completion

### For Advanced Users
**Tools reference →** [[Obsidian Vault Reorganizer - MCP Tools Reference]]
- All MCP tools documented
- Parameter details
- Usage examples

**Search patterns →** [[Obsidian Vault Reorganizer - JsonLogic Queries]]
- Complex search queries
- JsonLogic examples
- Advanced filtering

**Python utilities →** [[Obsidian Vault Reorganizer - Helper Functions]]
- Reusable code
- Helper classes
- Integration examples

---

## Common Use Cases

### Use Case 1: Clean Up Messy Vault
You have hundreds of notes with:
- Inconsistent frontmatter
- Random folder structure
- Orphaned notes everywhere

**Solution:**
1. Run Phase 1 to analyze
2. Use Phase 2 to remove empty notes
3. Apply Phase 3 for frontmatter standardization
4. Execute Phase 4 to link orphans
5. Organize with Phase 5

### Use Case 2: Migrate to New Structure
You want to reorganize your vault with:
- New folder hierarchy
- Different categories
- Updated frontmatter schema

**Solution:**
1. Skip Phase 2 (no deletion needed)
2. Run Phase 3 to update frontmatter
3. Define new folder structure
4. Execute Phase 5 to reorganize

### Use Case 3: Fix Orphaned Notes
You have many notes without backlinks:
- Notes aren't connected
- Graph view shows isolated nodes
- Hard to discover related content

**Solution:**
1. Run Phase 1 to find orphans
2. Execute Phase 4 only (backlink identification)
3. Optionally add bidirectional links
4. Verify with graph query

### Use Case 4: Standardize Existing Vault
Your vault needs:
- Consistent frontmatter
- Proper categorization
- No structural changes

**Solution:**
1. Run Phase 1 for analysis
2. Execute Phase 3 for frontmatter
3. Skip Phase 5 (no folder changes)
4. Verify with Phase 6

---

## Safety & Best Practices

### Before You Start
✅ **Full vault backup** - Create complete backup
✅ **Close Obsidian** - Prevent file locks
✅ **Test environment** - Try on small subset first
✅ **Review workflow** - Understand each phase
✅ **Define standards** - Plan folder structure and frontmatter

### During Execution
✅ **Preview operations** - Review before confirming
✅ **Take breaks** - Don't rush through phases
✅ **Keep logs** - Document all operations
✅ **Verify incrementally** - Check after each phase
✅ **Stop on errors** - Don't continue if issues arise

### After Completion
✅ **Final verification** - Run all checks
✅ **Test in Obsidian** - Open and verify vault
✅ **Check graph view** - Verify connections
✅ **Archive logs** - Save operation logs
✅ **Document changes** - Update vault documentation

---

## Troubleshooting

### Issue: MCP Tools Not Working
**Symptoms:** Tools return errors or don't connect
**Solution:**
- Verify Obsidian MCP server is running
- Check server configuration
- Restart MCP server
- Verify tool names and parameters

### Issue: Broken Links After Reorganization
**Symptoms:** Wikilinks don't work after moving files
**Solution:**
- Run Phase 5.6 (Update Wikilinks)
- Use `obsidian_graph_query` to find broken links
- Manually fix any remaining issues
- Consider using relative paths

### Issue: Lost Data After Deletion
**Symptoms:** Accidentally deleted important notes
**Solution:**
- Restore from backup (this is why we backup!)
- Check deletion log for content
- Review preview step procedure
- Adjust confirmation settings

### Issue: Performance Problems
**Symptoms:** Operations take too long
**Solution:**
- Reduce batch size
- Process vault in segments
- Use complex_search instead of loading all files
- Run during off-hours for large vaults

### Issue: Invalid Frontmatter
**Symptoms:** Notes don't display correctly
**Solution:**
- Verify YAML syntax
- Check for special characters
- Use proper list/array format
- Validate with YAML parser

---

## Customization

### Custom Frontmatter Template
Edit the template in Phase 3 to match your needs:

```yaml
---
title: {{filename}}
created: {{date}}
modified: {{date}}
tags: []
categories: []
status: draft
author: {{your-name}}
project: {{project-name}}
backlinks: []
---
```

### Custom Folder Structure
Define your structure in Phase 5:

```
/Projects
  /Active
  /Completed
  /Ideas
/Areas
  /Work
  /Personal
  /Learning
/Resources
  /Articles
  /Books
  /Videos
/Archives
  /2024
  /2023
```

### Custom Categories
Map categories to folders:

```python
category_mapping = {
    'python': 'Development/Python',
    'javascript': 'Development/JavaScript',
    'design': 'Creative/Design',
    'writing': 'Creative/Writing',
    'research': 'Knowledge/Research',
    'notes': 'Knowledge/Notes'
}
```

---

## Advanced Usage

### Automation with Python
Use the helper functions to automate:

```python
from vault_helpers import VaultAnalyzer, BatchProcessor

# Analyze vault
analyzer = VaultAnalyzer()
results = analyzer.analyze_vault()

# Process in batches
processor = BatchProcessor()
processor.process_with_progress(
    items=results['no_frontmatter'],
    process_func=add_frontmatter,
    batch_size=20
)
```

### Integration with Smart Connections
After reorganization:
1. Rebuild Smart Connections index
2. Verify semantic connections
3. Use new folder structure for better suggestions

### Scheduled Maintenance
Run quarterly to maintain organization:
1. Phase 1: Check for new orphans
2. Phase 3: Update frontmatter dates
3. Phase 4: Link new notes
4. Phase 5: Reorganize if needed

---

## FAQ

**Q: Will this break my vault?**
A: Not if you follow the safety procedures (backup, preview, confirm). The workflow is designed with multiple safety checkpoints.

**Q: How long does it take?**
A: Depends on vault size:
- Small (<100 notes): 30-60 minutes
- Medium (100-500 notes): 1-2 hours
- Large (500-1000 notes): 2-4 hours
- Very large (>1000 notes): Consider running overnight

**Q: Can I stop and resume?**
A: Yes! Each phase is independent. Complete one phase, verify, then continue when ready.

**Q: Will my tags be preserved?**
A: Yes. Frontmatter addition preserves existing metadata. Inline tags (#tag) are extracted and added to frontmatter.

**Q: What about plugins?**
A: Close Obsidian during reorganization to prevent plugin conflicts. Plugins work normally after reorganization.

**Q: Can I undo changes?**
A: Partial undo via operation logs. Full undo via backup restoration. This is why backup is critical!

---

## Support & Resources

### Documentation
- [[Obsidian Vault Reorganizer - Complete Workflow]] - Full process documentation
- [[Obsidian Vault Reorganizer - MCP Tools Reference]] - Tool documentation
- [[Obsidian Vault Reorganizer - JsonLogic Queries]] - Advanced search patterns

### External Resources
- [Obsidian Documentation](https://help.obsidian.md/)
- [MCP Documentation](https://modelcontextprotocol.io/)
- [JsonLogic Documentation](https://jsonlogic.com/)

### Community
- Obsidian Forums
- Obsidian Discord
- MCP GitHub Repository

---

## Version History

**v1.0** (2025-10-25)
- Initial release
- 5-phase workflow
- Complete MCP tools integration
- Python helper functions
- JsonLogic query examples

---

## License & Attribution

This skill package is designed for use with Claude AI and the Obsidian MCP server. Feel free to adapt and customize for your needs.

**Created:** 2025-10-25
**Author:** Claude + You
**Tools:** Obsidian MCP, Claude AI, Python

---

## Next Steps

🎯 **Ready to start?**

1. Read [[Obsidian Vault Reorganizer - Overview]]
2. Backup your vault
3. Open [[Obsidian Vault Reorganizer - Workflow Checklist]]
4. Begin Phase 1

🎓 **Want to learn more?**

1. Study [[Obsidian Vault Reorganizer - MCP Tools Reference]]
2. Experiment with [[Obsidian Vault Reorganizer - JsonLogic Queries]]
3. Explore [[Obsidian Vault Reorganizer - Helper Functions]]

💡 **Have questions?**

- Review this README
- Check the FAQ section
- Consult the workflow documentation
- Test on a small vault first

---

## Feedback & Improvements

As you use this skill package:
- Document what works well
- Note any issues or challenges
- Suggest improvements
- Share your customizations

Update this README with your learnings to help future you!

---

**Happy Organizing! 📚✨**
