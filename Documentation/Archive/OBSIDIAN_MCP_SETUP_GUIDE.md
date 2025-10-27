# 🔧 Obsidian MCP Server Setup Guide

## 🎯 **Issue Identified**

The `obsidian_patch_content` tool requires:
1. **Obsidian REST API Plugin** installed in Obsidian
2. **API Key** configured
3. **MCP Server** properly configured in Claude Desktop

## 🚀 **Setup Instructions**

### **Step 1: Install Obsidian REST API Plugin**

1. **Open Obsidian**
2. **Go to Settings** → **Community Plugins**
3. **Browse** → Search for "REST API"
4. **Install** the "REST API" plugin by Coddingtonbear
5. **Enable** the plugin

### **Step 2: Configure REST API Plugin**

1. **Go to Settings** → **Community Plugins** → **REST API**
2. **Enable** "Enable REST API"
3. **Set Port** (default: 27123)
4. **Generate API Key** or set a custom one
5. **Note the API Key** - you'll need this for the MCP server

### **Step 3: Update Claude Desktop Configuration**

Add the Obsidian MCP server to your configuration:

```json
{
  "mcpServers": {
    "docker-gateway": {
      "command": "docker",
      "args": ["mcp", "gateway", "run"]
    },
    "text-editor": {
      "command": "uvx",
      "args": ["mcp-text-editor"]
    },
    "n8n-mcp": {
      "command": "/Users/michel/.nvm/versions/node/v20.19.5/bin/node",
      "args": ["/Users/michel/Documents/MCP_Servers/n8n-mcp/dist/mcp/index.js"],
      "env": {
        "MCP_MODE": "stdio",
        "LOG_LEVEL": "error",
        "DISABLE_CONSOLE_OUTPUT": "true"
      }
    },
    "mem0": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/michel/Documents/MCP_Servers/mem0-mcp",
        "run",
        "main.py",
        "--stdio"
      ],
      "env": {
        "TRANSPORT": "stdio",
        "LLM_PROVIDER": "claude",
        "MEM0_MODE": "local",
        "MEMORY_STORAGE_PATH": "./mem0_mcp_db",
        "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2"
      }
    },
    "openrouterai": {
      "command": "/opt/homebrew/bin/npx",
      "args": ["-y", "@mcpservers/openrouterai"],
      "env": {
        "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
        "OPENROUTER_API_KEY": "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",
        "OPENROUTER_DEFAULT_MODEL": "qwen/qwen2.5-vl-32b-instruct:free",
        "OPENROUTER_MAX_TOKENS": "2048",
        "OPENROUTER_PROVIDER_QUANTIZATIONS": "fp16,int8",
        "OPENROUTER_PROVIDER_IGNORE": "openai,anthropic",
        "MCP_MODE": "stdio"
      },
      "timeout": 30000
    },
    "obsidian-rag": {
      "command": "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/venv/bin/python",
      "args": ["/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/obsidian_rag_mcp_fixed.py"],
      "env": {
        "VAULT_PATH": "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel",
        "LIGHTRAG_DIR": "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/lightrag_db"
      }
    },
    "obsidian-mcp": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--network", "host",
        "-v", "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel:/vault",
        "-e", "OBSIDIAN_API_KEY=YOUR_API_KEY_HERE",
        "-e", "OBSIDIAN_API_URL=http://localhost:27123",
        "mcp/obsidian"
      ]
    }
  }
}
```

### **Step 4: Replace API Key**

Replace `YOUR_API_KEY_HERE` with the actual API key from the Obsidian REST API plugin.

### **Step 5: Restart Claude Desktop**

1. **Quit Claude Desktop** completely
2. **Restart Claude Desktop**
3. **Check MCP Status** - You should see "obsidian-mcp" connected

## 🛠️ **Available Obsidian Tools**

Once configured, you'll have access to:

- **`obsidian_patch_content`** - Insert content into existing notes
- **`obsidian_append_content`** - Append content to files
- **`obsidian_get_file_contents`** - Get file contents
- **`obsidian_simple_search`** - Search vault
- **`obsidian_complex_search`** - Advanced search with JsonLogic
- **`obsidian_list_files_in_vault`** - List all files
- **`obsidian_delete_file`** - Delete files
- And more...

## 🔍 **Troubleshooting**

### **If Tools Still Don't Work:**

#### **1. Check Obsidian REST API Plugin**
- Ensure it's enabled and running
- Check the port (default: 27123)
- Verify API key is set

#### **2. Test REST API Connection**
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:27123/vault/
```

#### **3. Check Docker Container**
```bash
docker logs $(docker ps -q --filter ancestor=mcp/obsidian)
```

#### **4. Verify Vault Path**
- Ensure the vault path in Docker volume mount is correct
- Check that Obsidian can access the vault

## 🎯 **Expected Results**

After setup, you should be able to:

1. **Patch Content**: Use `obsidian_patch_content` to insert content into notes
2. **Search Vault**: Use `obsidian_simple_search` for text search
3. **Get File Contents**: Use `obsidian_get_file_contents` to read files
4. **Manage Files**: Use other Obsidian tools for file operations

## 💡 **Key Points**

- **Two MCP Servers**: You'll have both `obsidian-rag` (for AI search) and `obsidian-mcp` (for file operations)
- **REST API Required**: The Obsidian MCP needs the REST API plugin
- **API Key Security**: Keep your API key secure
- **Vault Access**: Ensure proper vault path configuration

## 🚀 **Next Steps**

1. **Install REST API Plugin** in Obsidian
2. **Get API Key** from plugin settings
3. **Update Claude Desktop Config** with Obsidian MCP server
4. **Replace API Key** in configuration
5. **Restart Claude Desktop**
6. **Test `obsidian_patch_content`** tool

This should resolve your "invalid-target" errors! 🎉





