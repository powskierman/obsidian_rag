#!/usr/bin/env python3
"""OpenAI-compatible chat endpoint backed by mlx_lm for LightRAG tests."""

import os
import time
import uuid
from typing import List, Optional
import threading

from fastapi import FastAPI, HTTPException
from mlx_lm import generate, load
from pydantic import BaseModel
import logging

MODEL_ID = os.getenv("MLX_MODEL_ID", "mlx-community/Mistral-22B-v0.2-4bit")
HOST = os.getenv("MLX_HOST", "0.0.0.0")
PORT = int(os.getenv("MLX_PORT", "8003"))

EXTRACTION_PROMPT = """
You are an information extraction engine.

Extract entities and relationships from the text below.
Return ONLY valid JSON.
Do not explain.

JSON format:
{{
  "entities": [{{"name": "...", "type": "..."}}],
  "relations": [{{"source": "...", "relation": "...", "target": "..."}}]
}}

TEXT:
{chunk}
"""

model, tokenizer = load(MODEL_ID)
logger = logging.getLogger("mlx_openai_server")
_generate_lock = threading.Lock()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.1
    top_p: Optional[float] = 0.9
    max_tokens: Optional[int] = 1024
    stream: Optional[bool] = False


app = FastAPI()


@app.post("/v1/chat/completions")
def chat_completions(req: ChatCompletionRequest):
    if req.stream:
        raise HTTPException(400, "Streaming not supported")

    chunk = "\n".join(
        m.content for m in req.messages if m.role.lower() in ("user", "system")
    )
    prompt = EXTRACTION_PROMPT.format(chunk=chunk)

    t0 = time.time()
    try:
        # MLX generation can segfault under concurrent access in some builds.
        # Serialize generation calls for stability during indexing throughput tests.
        with _generate_lock:
            result = generate(
                model,
                tokenizer,
                prompt=prompt,
                max_tokens=min(req.max_tokens or 512, 1024),
            )
    except Exception as e:
        logger.exception("MLX generation failed")
        result = '{"entities": [], "relations": []}'

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL_ID,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "time_seconds": round(time.time() - t0, 3),
        },
    }


@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [{"id": MODEL_ID, "object": "model", "owned_by": "local-mlx"}],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)
