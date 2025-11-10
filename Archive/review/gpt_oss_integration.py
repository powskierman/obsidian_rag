#!/usr/bin/env python3
"""
GPT-OSS Compatible Functions for LightRAG
Provides OpenAI-compatible API calls for GPT-OSS Docker Model Runner
Includes robust error handling for:
- Malformed JSON responses
- Model runner crashes
- Payload validation
"""

import os
import requests
import json
import logging
from typing import List, Optional
import re

logger = logging.getLogger(__name__)

async def gpt_oss_model_complete(
    prompt: str,
    system_prompt: Optional[str] = None,
    history_messages: List = None,
    host: str = None,
    model: str = None,
    **kwargs
) -> str:
    """
    GPT-OSS model completion using OpenAI-compatible API
    
    Args:
        prompt: User prompt
        system_prompt: System prompt (optional)
        history_messages: Conversation history (optional)
        host: GPT-OSS endpoint (e.g., http://host.docker.internal:12434/engines/llama.cpp)
        model: Model name (e.g., ai/gpt-oss:latest)
        **kwargs: Additional options (temperature, max_tokens, etc.)
    
    Returns:
        Generated response text
    """
    if host is None:
        host = os.getenv("GPT_OSS_HOST", "http://host.docker.internal:12434/engines/llama.cpp")
    
    if model is None:
        model = os.getenv("LLM_MODEL", "ai/gpt-oss:latest")
    
    # Build messages list - aggressively limit message lengths to avoid context shift issues
    messages = []
    
    # Limit system prompt length (GPT-OSS has strict context limits)
    if system_prompt:
        # Aggressively truncate system prompt to avoid context shift
        max_system_length = 500  # Reduced from 1000
        if len(system_prompt) > max_system_length:
            system_prompt = system_prompt[:max_system_length] + "..."
        messages.append({"role": "system", "content": system_prompt})
    
    # Limit history messages to avoid context issues - be more aggressive
    if history_messages:
        # Only keep last 1 message from history to minimize context
        limited_history = history_messages[-1:] if len(history_messages) > 1 else history_messages
        # Also truncate each history message
        truncated_history = []
        for msg in limited_history:
            if isinstance(msg, dict) and "content" in msg:
                content = msg["content"]
                if len(content) > 1000:  # Truncate history messages
                    content = content[:1000] + "..."
                truncated_history.append({**msg, "content": content})
            else:
                truncated_history.append(msg)
        messages.extend(truncated_history)
    
    # Limit user prompt length more aggressively
    max_prompt_length = 2000  # Reduced from 4000
    if len(prompt) > max_prompt_length:
        logger.warning(f"Prompt truncated from {len(prompt)} to {max_prompt_length} chars to avoid context shift")
        prompt = prompt[:max_prompt_length] + "..."
    messages.append({"role": "user", "content": prompt})
    
    # Prepare request
    url = f"{host}/v1/chat/completions"
    
    # Build payload - be careful with parameter names
    payload = {
        "model": model,
        "messages": messages,
    }
    
    # Handle max_tokens - keep it very small to avoid context shift issues
    max_tokens = kwargs.get("max_tokens")
    if max_tokens:
        # Cap at very small limit to avoid GPT-OSS "context shift disabled" errors
        payload["max_tokens"] = min(int(max_tokens), 512)  # Reduced from 2048
    else:
        # Default very small max_tokens for GPT-OSS
        payload["max_tokens"] = 512  # Reduced from 1024
    
    # Handle temperature
    temperature = kwargs.get("temperature", 0.7)
    if "options" in kwargs and "temperature" in kwargs["options"]:
        temperature = kwargs["options"]["temperature"]
    if temperature is not None:
        payload["temperature"] = float(temperature)
    
    # Remove any None values that might cause issues
    payload = {k: v for k, v in payload.items() if v is not None}
    
    # Validate payload before sending
    try:
        json.dumps(payload)  # Test if payload is JSON serializable
    except (TypeError, ValueError) as e:
        logger.error(f"Invalid payload (not JSON serializable): {e}")
        raise ValueError(f"Payload validation failed: {e}")
    
    # Retry logic for 500 errors
    max_retries = 3
    retry_delay = 2  # seconds
    
    import asyncio
    
    for attempt in range(max_retries):
        try:
            # Run the request in a thread pool to make it async-compatible
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(url, json=payload, timeout=300)
            )
            
            # Log request details for debugging
            if response.status_code >= 400:
                error_detail = response.text[:200] if response.text else "No error message"
                logger.warning(f"GPT-OSS API error {response.status_code} (attempt {attempt + 1}/{max_retries}): {error_detail}")
                if response.status_code == 500 and attempt < max_retries - 1:
                    # Wait before retrying on 500 errors
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
            
            response.raise_for_status()
            
            # Parse response with robust JSON handling for malformed JSON
            try:
                result = response.json()
            except json.JSONDecodeError as e:
                logger.error(f"Malformed JSON response from GPT-OSS (model runner may have crashed): {e}")
                logger.error(f"Response text (first 500 chars): {response.text[:500]}")
                # Try to extract JSON from response if it's embedded in text
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group())
                        logger.warning("Extracted JSON from malformed response")
                    except json.JSONDecodeError:
                        raise ValueError(f"Could not parse malformed JSON response (model runner may have crashed): {e}")
                else:
                    raise ValueError(f"Response is not valid JSON (model runner may have crashed): {e}")
            
            # Extract response text with validation
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")
                if not content:
                    logger.error(f"Empty content in GPT-OSS response: {result}")
                    return ""
                return content
            else:
                logger.error(f"Unexpected GPT-OSS response format: {result}")
                return ""
        
        except requests.exceptions.HTTPError as e:
            # If it's a 500 error and we have retries left, retry
            if e.response.status_code == 500 and attempt < max_retries - 1:
                logger.warning(f"Retrying after 500 error (attempt {attempt + 1}/{max_retries})...")
                logger.warning("This may indicate model runner crash - will retry after delay")
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue
            else:
                # Provide more detailed error information
                error_msg = f"GPT-OSS API HTTP error: {e.response.status_code}"
                if hasattr(e.response, 'text'):
                    error_msg += f" - {e.response.text[:200]}"
                logger.error(error_msg)
                logger.debug(f"Request URL: {url}")
                logger.debug(f"Request payload: {payload}")
                raise
        except requests.exceptions.RequestException as e:
            # Retry on connection errors (may indicate model runner crash)
            if attempt < max_retries - 1:
                logger.warning(f"Retrying after connection error (attempt {attempt + 1}/{max_retries}): {e}")
                logger.warning("This may indicate model runner crash - will retry after delay")
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue
            else:
                logger.error(f"GPT-OSS API error after {max_retries} attempts (model runner may have crashed): {e}")
                raise
        except ValueError as e:
            # Malformed JSON - don't retry, this is a model issue
            logger.error(f"Malformed JSON from GPT-OSS (model runner may have crashed): {e}")
            raise


def gpt_oss_embed(
    texts: List[str],
    embed_model: str = None,
    host: str = None
) -> List[List[float]]:
    """
    GPT-OSS embeddings - falls back to Ollama since GPT-OSS may not have embedding models
    
    Args:
        texts: List of texts to embed
        embed_model: Embedding model name
        host: GPT-OSS endpoint (not used, falls back to Ollama)
    
    Returns:
        List of embedding vectors
    """
    # GPT-OSS typically doesn't have embedding models, so use Ollama
    ollama_host = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
    
    if embed_model is None:
        embed_model = os.getenv("EMBED_MODEL", "nomic-embed-text")
    
    logger.info(f"Using Ollama for embeddings: {ollama_host} (GPT-OSS doesn't provide embeddings)")
    
    from lightrag.llm.ollama import ollama_embed
    return ollama_embed(texts, embed_model=embed_model, host=ollama_host)


def is_gpt_oss_endpoint(host: str) -> bool:
    """
    Check if the host is a GPT-OSS endpoint
    
    Args:
        host: Endpoint URL
    
    Returns:
        True if GPT-OSS endpoint format detected
    """
    if not host:
        return False
    
    # GPT-OSS uses /engines/llama.cpp in the path
    return "/engines/llama.cpp" in host or "/v1" in host or ":12434" in host


def get_model_func(host: str):
    """
    Get the appropriate model function based on endpoint type
    
    Args:
        host: LLM endpoint URL
    
    Returns:
        Model completion function (gpt_oss_model_complete or ollama_model_complete)
    """
    if is_gpt_oss_endpoint(host):
        logger.info(f"Using GPT-OSS endpoint: {host}")
        return gpt_oss_model_complete
    else:
        logger.info(f"Using Ollama endpoint: {host}")
        from lightrag.llm.ollama import ollama_model_complete
        return ollama_model_complete


def get_embed_func(host: str):
    """
    Get the appropriate embedding function based on endpoint type
    
    Args:
        host: Embedding endpoint URL
    
    Returns:
        Embedding function (gpt_oss_embed or ollama_embed)
    """
    if is_gpt_oss_endpoint(host):
        logger.info(f"Using GPT-OSS embeddings: {host}")
        return gpt_oss_embed
    else:
        logger.info(f"Using Ollama embeddings: {host}")
        from lightrag.llm.ollama import ollama_embed
        return ollama_embed
