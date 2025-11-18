# Archive Directory

This directory contains files that are no longer actively used but kept for reference.

## Structure

- **deprecated/** - Old services and files no longer in use
  - LightRAG service files
  - FastGraph service files
  - Alternative UI implementations
  - Old scanner implementations

- **tests/** - Test files and test outputs
  - Test scripts
  - Search result files
  - Query utilities

- **logs/** - Old log files
  - Service logs
  - Indexing logs
  - Application logs

- **old_databases/** - Old database directories
  - lightrag_db/ - LightRAG database (no longer used)

- **old_venvs/** - Old Python virtual environments
  - venv_python313/ - Python 3.13 virtual environment

- **old_implementations/** - Previous implementation versions
  - ClaudeRAG/ - Original ClaudeRAG implementation

- **review/** - Files that need review before deletion
  - Generic Dockerfile
  - Integration scripts
  - Utility scripts

## When to Delete

These files can be safely deleted if:
- You're certain they won't be needed
- You have backups
- You want to free up disk space

## Restoration

If you need to restore any file:
1. Copy it back to the root directory
2. Update any references if needed
3. Test that it works

---

**Archived**: November 7, 2025  
**Reason**: Codebase cleanup after removing LightRAG and FastGraph services

