# Docker Troubleshooting Guide

## Code Changes Not Reflected in Streamlit UI

**Symptom**: Local scripts work correctly, but Streamlit UI in Docker shows old behavior.

**Cause**: Docker containers use cached images and don't automatically pick up code changes.

**Solution**:

```bash
# Rebuild specific container
docker-compose build streamlit-ui --no-cache
docker-compose up -d streamlit-ui

# OR rebuild all containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

**Key Points**:
- `--no-cache` forces fresh rebuild
- Volume mounts sync specific files, but imported modules need rebuild
- Always rebuild after modifying Python dependencies or core logic

## Orphaned Container Errors

**Symptom**: Error about mounting non-existent files like `index_vault_lightrag.py`

**Cause**: Old compose configurations cached in Docker

**Solution**:

```bash
# Remove orphaned containers
docker-compose down --remove-orphans

# Or manually remove
docker ps -a | grep obsidian | awk '{print $1}' | xargs docker rm -f
```

## Web Search Not Triggering

**Symptom**: Steps marked as "web" search return 0 documents

**Check**:
1. Verify `TAVILY_API_KEY` in `.env` file
2. Rebuild containers to pick up `.env` changes
3. Check supervisor logs for "DEBUG: Web Query:" messages

**If still failing**: Run `reproduce_issue.py` locally to verify fix, then rebuild Docker containers.
