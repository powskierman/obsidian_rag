#!/usr/bin/env python3
"""
Validate Claude API Key
Tests if the ANTHROPIC_API_KEY is valid by making a test API call.
"""

import os
import sys
from anthropic import Anthropic
from anthropic import APIError

def validate_api_key(api_key: str = None) -> tuple[bool, str]:
    """
    Validate Claude API key by making a test API call.
    
    Returns:
        (is_valid, message)
    """
    if not api_key:
        api_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not api_key:
        return False, "❌ ANTHROPIC_API_KEY not set"
    
    if not api_key.startswith("sk-ant-"):
        return False, f"❌ Invalid API key format. Should start with 'sk-ant-', got: {api_key[:10]}..."
    
    try:
        client = Anthropic(api_key=api_key)
        
        # Make a minimal test call
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        
        # If we get here, the key is valid
        return True, f"✅ API key is VALID! (Model: {response.model})"
        
    except APIError as e:
        if e.status_code == 401:
            return False, f"❌ API key is INVALID (401 Unauthorized): {e.message}"
        elif e.status_code == 403:
            return False, f"❌ API key is FORBIDDEN (403): {e.message}"
        else:
            return False, f"❌ API Error ({e.status_code}): {e.message}"
    except Exception as e:
        return False, f"❌ Error validating key: {str(e)}"


if __name__ == "__main__":
    print("🔍 Validating Claude API Key...\n")
    
    # Try to get key from .env file first
    api_key = None
    env_file = ".env"
    
    if os.path.exists(env_file):
        print(f"📄 Reading from {env_file}...")
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY=") and not line.startswith("#"):
                    api_key = line.split("=", 1)[1].strip()
                    # Remove quotes if present
                    api_key = api_key.strip('"').strip("'")
                    break
    
    # Fall back to environment variable
    if not api_key:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            print("📄 Reading from environment variable...")
    
    if not api_key:
        print("❌ No API key found!")
        print("\nSet it in one of these ways:")
        print("1. Create/update .env file: ANTHROPIC_API_KEY=sk-ant-...")
        print("2. Export environment variable: export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)
    
    # Show first/last few chars for verification
    if len(api_key) > 20:
        key_preview = f"{api_key[:15]}...{api_key[-10:]}"
    else:
        key_preview = api_key[:10] + "..."
    
    print(f"🔑 Key preview: {key_preview}")
    print()
    
    # Validate
    is_valid, message = validate_api_key(api_key)
    print(message)
    
    if is_valid:
        print("\n✅ Your API key is working correctly!")
        sys.exit(0)
    else:
        print("\n💡 To fix this:")
        print("1. Get a new API key from: https://console.anthropic.com/")
        print("2. Update your .env file with: ANTHROPIC_API_KEY=sk-ant-...")
        print("3. Restart your Docker containers: docker-compose restart")
        sys.exit(1)

