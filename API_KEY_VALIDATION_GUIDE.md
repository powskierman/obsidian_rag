# Claude API Key Validation Guide

## Problem
You were seeing "✅ Claude API key configured" in Streamlit but getting 401 authentication errors. This happened because:

1. **Streamlit only checked if the key exists**, not if it's valid
2. **Docker container had a cached/old API key** that didn't match your `.env` file
3. **Restarting the container** was needed to pick up the new key from `.env`

## Solution

### 1. Validate Your API Key

Use the validation script to test your key:

```bash
# From project root
python3 validate_claude_api_key.py
```

Or test directly in Docker:

```bash
docker-compose exec streamlit-ui python3 -c "
from anthropic import Anthropic
import os
client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
r = client.messages.create(
    model='claude-3-5-haiku-20241022',
    max_tokens=10,
    messages=[{'role': 'user', 'content': 'Hi'}]
)
print('✅ API key is valid!')
"
```

### 2. Update Your `.env` File

Edit `.env` in the project root:

```bash
ANTHROPIC_API_KEY=sk-ant-api03-XXXXXXXXXXXXXXXXXXXXXXXX
```

Get your key from: https://console.anthropic.com/

### 3. Restart Docker Containers

After updating `.env`, restart to pick up the new key:

```bash
# Option 1: Restart just Streamlit
docker-compose restart streamlit-ui

# Option 2: Stop and recreate (more thorough)
docker-compose stop streamlit-ui
docker-compose up -d streamlit-ui

# Option 3: Restart all services
docker-compose restart
```

### 4. Verify the Key is Loaded

Check that the container has the correct key:

```bash
# Compare keys
KEY_ENV=$(grep "^ANTHROPIC_API_KEY=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")
KEY_DOCKER=$(docker-compose exec -T streamlit-ui printenv ANTHROPIC_API_KEY | tr -d '\r')

if [ "$KEY_ENV" = "$KEY_DOCKER" ]; then
    echo "✅ Keys match!"
else
    echo "❌ Keys don't match - restart the container"
fi
```

## Improvements Made

1. **Enhanced Streamlit Validation**: Now actually tests the API key, not just checks if it exists
2. **Better Error Messages**: Shows specific 401 errors with helpful instructions
3. **Validation Script**: `validate_claude_api_key.py` for easy testing
4. **Cached Validation**: Streamlit caches validation results to avoid repeated API calls

## Troubleshooting

### Still getting 401 errors?

1. **Verify key format**: Should start with `sk-ant-api03-`
2. **Check key is valid**: Run `validate_claude_api_key.py`
3. **Ensure container restarted**: Use `docker-compose stop` then `up -d` (not just `restart`)
4. **Check for typos**: No extra spaces or quotes in `.env` file
5. **Verify key is active**: Check your Anthropic console

### Keys don't match between .env and container?

```bash
# Force recreate container
docker-compose stop streamlit-ui
docker-compose rm -f streamlit-ui
docker-compose up -d streamlit-ui
```

### Streamlit shows "configured" but still fails?

The new validation will catch this immediately. If you see "✅ Claude API key configured and validated", the key is definitely working.

