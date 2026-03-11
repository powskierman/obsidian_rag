# Mac Mini Quick Start

This is a minimal checklist for the Mac mini setup.

1. Ensure the repo and vault are present locally.
2. Set `OBSIDIAN_VAULT_PATH` in `.env`.
3. Start services:
   ```bash
   docker compose up -d
   ```
4. Verify health:
   ```bash
   curl -s http://localhost:4000/api/v1/health
   ```

If the vault is stored in iCloud, confirm the files are fully downloaded locally.
