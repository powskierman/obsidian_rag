
import os
import time
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure GenAI
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    # Try reading from .env manually if load_dotenv failed (current dir might differ)
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("GEMINI_API_KEY="):
                api_key = line.strip().split("=", 1)[1]
                break

print(f"API Key found: {api_key[:5]}...")
genai.configure(api_key=api_key)

model_name = "gemini-3-pro-preview"
print(f"Initializing model: {model_name}")
model = genai.GenerativeModel(model_name)

# The EXACT prompt causing the issue (simplified slightly for test but structurally identical)
prompt = """You are an expert Research Assistant helping Michel understand his Obsidian knowledge base.

Context from notes and web:
[Some context about ESP32 protocols]

User question: esp32 protocols

REQUIREMENTS:
1. **Structure**: Use `##` headers. Start with an Executive Summary if complex.
2. **Content**:
   - Answer the user's question directly.
   - Synthesize findings from both Vault and Web.
   - **Vault Citations**: Cite vault sources as `[[Note Name]]`.
   - **Web Citations**: Cite web sources as `[Title](URL)`.
3. **Deep Thinking**:
   - If the query is technical/engineering, use "Hardware Pathology" (diagnosing faults) and "Treatment" (fixes) metaphors where appropriate.
   - If medical, focus on "Clinical Implications" and "Treatment Considerations".
   - Highlighting specific "Known Defects" or "Common Pitfalls" is highly valued.

Answer:"""

print("Sending prompt to Gemini...")
start = time.time()
try:
    response = model.generate_content(prompt)
    duration = time.time() - start
    print(f"Success! Time taken: {duration:.2f}s")
    print("Response sample:", response.text[:200])
except Exception as e:
    print(f"Error: {e}")
