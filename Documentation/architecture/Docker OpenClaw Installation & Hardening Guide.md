# OpenClaw Installation & Hardening Guide

This guide outlines the procedure to install a secure, local-only OpenClaw instance on a dedicated Mac mini, integrated with your existing `obsidian_rag` system for retrieval and Telegram for remote access.

## 1. Prerequisites & Hardening

Since this is a dedicated "server" exposed to Telegram, basic hardening is essential.

### MacOS Hardening

1. **Create a Dedicated User**: Create a standard user account (e.g., `openclaw_svc`) for running the services. Do not run as Admin.
2. **Enable FileVault**: Ensure disk encryption is on.
3. **Firewall**:
   - Go to **System Settings > Network > Firewall**.
   - Enable Firewall.
   - "Block all incoming connections" is usually too strict for local admin, but for a bot (which uses outbound long-polling), you *can* block incoming if you don't need SSH from outside.
   - **Recommendation**: Allow only SSH from local LAN.
4. **Auto-Updates**: Enable automatic security updates.
5. **Disable Unnecessary Services**: Turn off Sharing options (File Sharing, Screen Sharing) unless explicitly needed for management.

### Telegram Bot Setup

1. Open Telegram and message `@BotFather`.
2. Send `/newbot`.
3. Follow instructions to get your **Bot Token**. Save this securely.

## 2. Deployment Architecture (Docker)

We will use **Docker Compose** to run OpenClaw and Obsidian RAG as isolated services. This ensures:

- **Security**: Services are containerized.
- **Reliability**: Auto-restart on failure.
- **Networking**: Internal communication between OpenClaw and RAG without exposing ports to the host LAN.

<div style="page-break-after:always"></div>

### Directory Structure

Create a directory `/Users/michel/server/openclaw`:

```
mkdir -p ~/server/openclaw/config

cd ~/server/openclaw
```

## 3. Configuration

Create the following 

docker-compose.yml file in `~/server/openclaw`.

> **Note**: Replace paths with your actual paths.

```
services:
  # Service 1: OpenClaw (The Agent)
  openclaw:
    image: ghcr.io/openclaw/openclaw:latest
    container_name: openclaw
    restart: always

    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - OPENAI_API_KEY=${OPENAI_API_KEY} # Or local LLM URL
      - OBSIDIAN_VAULT_PATH=/data/vault
      # Configure MCP Connectors
      - MCP_HUBS=http://obsidian-rag:8811/mcp

    volumes:
      - ./config:/app/config
      - /Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/vault-test:/data/vault # Your Real Vault

    depends_on:
      - obsidian-rag

  # Service 2: Obsidian RAG (The Brain)
  obsidian-rag:
    build:
      context: /Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag
      dockerfile: Dockerfile
    container_name: obsidian-rag
    restart: always

    command: ["python", "src/mcp/obsidian_rag_unified_mcp.py", "--transport", "http", "--host", "0.0.0.0", "--port", "8811"]

    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - GEMINI_API_KEY=${GEMINI_API_KEY}

      # Point to the internal mount location
      - OBSIDIAN_VAULT_ROOT=/data/vault 

    volumes:
      # Mount the SAME vault so it can index/read
      - /Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/vault-test:/data/vault
      # Persist RAG databases (chroma, graph)
      - rag-data:/app/data

volumes:

  rag-data:
```



### Environment Variables

Create a .env file in the same directory:

```
TELEGRAM_BOT_TOKEN=your_telegram_token_here
OPENAI_API_KEY=your_openai_key_here
GEMINI_API_KEY=your_gemini_key_here
```

## 4. Integration Details

### A. Data Entry (Telegram -> Obsidian)

OpenClaw natively supports file system operations. By mounting your vault to `/data/vault`, OpenClaw can directly create markdown files.

- **Usage**: "Add a note to my inbox: [Content]"
- **Config**: You may need to set a "System Prompt" in OpenClaw config to tell it: "Always save new notes to /data/vault/00_Inbox with timestamped filenames."

### B. Data Retrieval (Telegram -> RAG)

We configured `MCP_HUBS` to point to `http://obsidian-rag:8811/mcp`.

- **Usage**: "What do I know about [Topic]?"
- **Flow**: OpenClaw sees the search_vault and query_knowledge_graph tools provided by the Obsidian RAG MCP server. It calls them, gets the JSON result, and summarizes it back to you on Telegram.

<div style="page-break-after:always"></div>

## 5. Launch

1. **Build and Run**:

   ```
   docker-compose up -d --build
   ```

2. **Verify**:

   - Check logs: `docker-compose logs -f`
   - Test Telegram: Send `/start` or "Hello" to your bot.

## 6. Maintenance

- **Updates**: Run `docker-compose pull && docker-compose up -d` to update OpenClaw. Rebuild `obsidian-rag` if you change its code.
- **Backups**: Ensure your iCloud Drive (where the vault lives) is backing up. The RAG indices (`rag-data` volume) are derivative and can be rebuilt, but you may want to back them up via script if generation takes a long time.

