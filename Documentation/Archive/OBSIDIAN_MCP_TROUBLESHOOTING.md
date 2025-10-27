# 🔧 Obsidian MCP Troubleshooting Guide

## 🎯 **Current Status**
- ✅ Obsidian is running
- ✅ Docker MCP container is running  
- ❌ REST API plugin not listening on port 27123
- ❌ `obsidian_patch_content` returning "invalid-target" errors

## 🚀 **Solution: Install & Configure REST API Plugin**

### **Step 1: Install REST API Plugin**

1. **Open Obsidian**
2. **Go to Settings** (gear icon) → **Community Plugins**
3. **Click "Browse"** (if not already there)
4. **Search for "REST API"**
5. **Find "REST API" by Coddingtonbear**
6. **Click "Install"**
7. **Click "Enable"**

### **Step 2: Configure REST API Plugin**

1. **Go to Settings** → **Community Plugins** → **REST API**
2. **Enable "Enable REST API"** (toggle ON)
3. **Set Port**: `27123` (default)
4. **Generate API Key** or use existing one
5. **Note the API Key** (should match what you have: `ca0b5a76021892751c363a853e65f4dfdcea643257b82794e02c5e57d1d2fedc`)

### **Step 3: Verify REST API is Working**

After enabling the plugin, test the connection:

```bash
curl -H "Authorization: Bearer ca0b5a76021892751c363a853e65f4dfdcea643257b82794e02c5e57d1d2fedc" http://localhost:27123/vault/
```

**Expected response**: Should return vault information, not connection error.

### **Step 4: Restart Claude Desktop**

1. **Quit Claude Desktop** completely
2. **Restart Claude Desktop**
3. **Check MCP Status** - "obsidian-mcp" should be connected

## 🔍 **Alternative Troubleshooting**

### **If REST API Plugin Still Doesn't Work:**

#### **Option 1: Check Plugin Installation**
- Go to **Settings** → **Community Plugins**
- Look for "REST API" in the **Installed Plugins** list
- If not there, reinstall it

#### **Option 2: Check Plugin Settings**
- Go to **Settings** → **Community Plugins** → **REST API**
- Ensure **"Enable REST API"** is toggled ON
- Check the port number (should be 27123)
- Verify API key matches your configuration

#### **Option 3: Check Obsidian Logs**
- Go to **Settings** → **About** → **Open Logs**
- Look for any REST API related errors

#### **Option 4: Try Different Port**
If port 27123 is blocked, try a different port:
1. Change port in REST API plugin settings (e.g., 27124)
2. Update the Docker configuration:
   ```json
   "-e", "OBSIDIAN_API_URL=http://localhost:27124"
   ```

### **If Still Having Issues:**

#### **Option 5: Manual Plugin Installation**
1. Download the plugin manually from: https://github.com/coddingtonbear/obsidian-api
2. Extract to: `~/.obsidian/plugins/obsidian-api/`
3. Restart Obsidian
4. Enable the plugin

#### **Option 6: Check Vault Path**
Ensure the vault path in Docker is correct:
```bash
ls -la "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
```

## 🧪 **Testing the Fix**

Once the REST API plugin is working, test these commands in Claude Desktop:

### **Basic Test**
```
"List files in my vault"
```

### **Patch Content Test**
```
"Patch content into my Home-Assistant MoC.md file"
```

### **Search Test**
```
"Search my vault for Home Assistant"
```

## 🎯 **Expected Results**

After fixing the REST API plugin:

1. **✅ `obsidian_patch_content`** - Should work without "invalid-target" errors
2. **✅ `obsidian_simple_search`** - Should return search results
3. **✅ `obsidian_get_file_contents`** - Should return file contents
4. **✅ `obsidian_list_files_in_vault`** - Should list vault files

## 💡 **Key Points**

- **REST API Plugin is Required**: The Docker MCP server needs this plugin to communicate with Obsidian
- **Plugin Must Be Enabled**: Just installing isn't enough - it must be enabled
- **Port Must Match**: The port in plugin settings must match the Docker configuration
- **API Key Must Match**: The API key must be the same in both places

## 🚀 **Next Steps**

1. **Install REST API Plugin** in Obsidian
2. **Enable and Configure** the plugin
3. **Test REST API Connection** with curl
4. **Restart Claude Desktop**
5. **Test `obsidian_patch_content`** tool

## 🔧 **Quick Fix Summary**

The root cause is: **REST API plugin not installed/enabled in Obsidian**

**Solution**: Install and enable the REST API plugin in Obsidian, then restart Claude Desktop.

This should completely resolve your "invalid-target" errors! 🎉





