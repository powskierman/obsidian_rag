# Auto Monitoring on Login

This project already includes a LaunchAgent installer. The watcher can now be started automatically on login by using the existing startup flow.

## Recommended Setup (macOS)
1) Install the LaunchAgent (starts services on login):
   - `Scripts/setup/install_launch_agent.sh`

2) Ensure the launch script points to the setup entrypoint:
   - `Scripts/setup/start_obsidian_rag.sh`

## Environment Notes
- The watcher uses `WATCHER_CHOICE` to pick scan mode (default: 3 = incremental scan then watch).
- To enable delete propagation, set `EMBEDDING_CLEAR_TOKEN` or `WATCHER_ADMIN_TOKEN` for the watcher process.

If using LaunchAgent, you can set environment variables via:
- `launchctl setenv EMBEDDING_CLEAR_TOKEN "<token>"`
- `launchctl setenv WATCHER_CHOICE 3`

## Logs
- LaunchAgent logs are written under `Scripts/setup/logs/` at runtime.
