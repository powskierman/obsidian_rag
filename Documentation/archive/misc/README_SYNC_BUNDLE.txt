Obsidian RAG sync bundle

Target: Canmore repo root
  /Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag

Apply steps on Canmore:
1) Unzip this bundle
2) Copy payload contents into repo root
   rsync -a payload/ "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/"
3) Ensure recovery scripts are executable
   chmod 755 Scripts/setup/recover_local_llm_and_gateway.sh Scripts/setup/recover_api_gateway_and_mlx.sh Scripts/setup/install_recovery_launch_agent.sh
4) Rebuild/restart services
   docker compose build --no-cache api-gateway webapp
   docker compose up -d --force-recreate api-gateway webapp
5) Hard refresh browser (Cmd+Shift+R)
