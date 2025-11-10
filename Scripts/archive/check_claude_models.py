#!/usr/bin/env python3
"""Check available Claude models"""

import os
import anthropic

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    print("❌ Set ANTHROPIC_API_KEY first")
    exit(1)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

print("🔍 Testing Claude models...\n")

models_to_test = [
    "claude-3-5-haiku-20241022",
    "claude-3-5-sonnet-20241022",
    "claude-haiku-4-5-20250122",
    "claude-3-haiku-20240307",
]

for model in models_to_test:
    try:
        response = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        print(f"✅ {model} - WORKS!")
    except anthropic.NotFoundError:
        print(f"❌ {model} - Not found")
    except Exception as e:
        print(f"⚠️  {model} - Error: {str(e)[:50]}")

print("\n💡 Use the working model name in your script")

