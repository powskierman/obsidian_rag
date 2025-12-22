import os
from openai import OpenAI
import sys

def test_connectivity():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ Error: OPENROUTER_API_KEY not set")
        return False
    
    print(f"Testing connectivity to OpenRouter with model: moonshotai/kimi-k2-0905...")
    
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    
    try:
        response = client.chat.completions.create(
            model="moonshotai/kimi-k2-0905",
            messages=[{"role": "user", "content": "Hello, respond with 'Connectivity OK' if you can hear me."}],
            max_tokens=10
        )
        print(f"✅ Response: {response.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    if test_connectivity():
        sys.exit(0)
    else:
        sys.exit(1)
