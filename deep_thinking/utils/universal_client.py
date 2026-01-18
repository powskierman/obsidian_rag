#!/usr/bin/env python3
"""
Universal LLM Client wrapper for Deep Thinking Agent.
Supports Anthropic (Claude), Google (Gemini), OpenRouter, and ChatGPT (OpenAI) APIs with a unified interface.
Mimics the Anthropic client interface (messages.create).
"""

import os
import requests
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class UniversalMessage:
    """Wrapper for message response to match Anthropic's structure"""
    def __init__(self, content_text: str):
        self.content = [type('Content', (), {'text': content_text})()]
        self.content_text = content_text

class UniversalClient:
    def __init__(self, provider: str = "claude", api_key: Optional[str] = None):
        self.provider = provider.lower()
        self.api_key = api_key
        
        # Initialize Anthropic client if needed
        if self.provider == "claude":
            try:
                from anthropic import Anthropic
                self.anthropic = Anthropic(api_key=api_key)
            except ImportError:
                print("Warning: anthropic package not installed")
                self.anthropic = None
        
        self.messages = self  # Emulate client.messages structure

    def create(self, model: str, messages: List[Dict[str, str]], 
               max_tokens: int = 4000, temperature: float = 0.7, 
               system: str = "") -> UniversalMessage:
        """
        Unified create method matching Anthropic's signature.
        """
        if self.provider == "claude":
            return self._create_claude(model, messages, max_tokens, temperature, system)
        elif self.provider == "gemini":
            return self._create_gemini(model, messages, max_tokens, temperature, system)
        elif self.provider == "openrouter":
            return self._create_openrouter(model, messages, max_tokens, temperature, system)
        elif self.provider in ("chatgpt", "openai"):
            return self._create_openai(model, messages, max_tokens, temperature, system)
        elif self.provider == "ollama":
            return self._create_ollama(model, messages, max_tokens, temperature, system)
        elif self.provider == "perplexity":
            return self._create_perplexity(model, messages, max_tokens, temperature, system)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _create_perplexity(self, model: str, messages: List[Dict[str, str]], 
                           max_tokens: int, temperature: float, system: str):
        api_key = self.api_key or os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            raise ValueError("PERPLEXITY_API_KEY not configured")
        
        # Default to a good online model
        if not model or "claude" in model or "gpt" in model:
            model = os.getenv("PERPLEXITY_MODEL", "llama-3.1-sonar-large-128k-online")

        pplx_messages = list(messages)
        if system:
            pplx_messages = [{"role": "system", "content": system}] + pplx_messages

        payload = {
            "model": model,
            "messages": pplx_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "return_citations": True  # Perplexity specific feature
        }

        try:
            response = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=60
            )

            if response.status_code != 200:
                error_msg = f"Perplexity API Error {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise ValueError(error_msg)

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("No choices returned from Perplexity")

            message = choices[0].get("message", {})
            content = message.get("content", "")
            
            # Perplexity returns citations which are useful
            citations = data.get("citations", [])
            if citations:
                # Append citations references if not present
                content += "\n\n**Perplexity Citations:**\n"
                for i, cit in enumerate(citations):
                    content += f"[{i+1}] {cit}\n"

            return UniversalMessage(content)
        except Exception as e:
            logger.error(f"Perplexity request failed: {e}")
            raise e

    def _create_claude(self, model: str, messages: List[Dict[str, str]], 
                       max_tokens: int, temperature: float, system: str):
        if not self.anthropic:
             raise ValueError("Anthropic client not initialized")
             
        # Map Gemini models to Claude if provider switched but model name stuck
        if "gemini" in model.lower():
            model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
            
        return self.anthropic.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages
        )

    def _create_gemini(self, model: str, messages: List[Dict[str, str]], 
                       max_tokens: int, temperature: float, system: str):
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        # Map Claude models to Gemini if provider switched but model name stuck
        if "claude" in model.lower():
            model = os.getenv("GEMINI_MODEL", "gemini-3-pro-preview")
            
        # Ensure model has 'models/' prefix or matches known ID
        if not model.startswith("models/") and not model.startswith("gemini-"):
             model = "gemini-3-pro-preview"


        # Construct prompt
        full_content = ""
        if system:
            full_content += f"System:\n{system}\n\n"
            
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            full_content += f"{role.capitalize()}:\n{content}\n\n"
            
        full_content += "Assistant:"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        
        # Gemini needs sufficient output tokens - ensure minimum of 8192
        output_tokens = max(max_tokens, 8192)
        
        payload = {
            "contents": [{
                "parts": [{"text": full_content}]
            }],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": output_tokens
            }
        }

        try:
            response = requests.post(
                url,
                headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=60
            )
            
            if response.status_code != 200:
                error_msg = f"Gemini API Error {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            data = response.json()
            logger.debug(f"Gemini raw response: {data}")
            
            candidates = data.get("candidates", [])
            if not candidates:
                error_detail = data.get("error", {}).get("message", "Unknown error")
                raise ValueError(f"No candidates returned from Gemini: {error_detail}")
            
            # Safely access the content parts
            content_obj = candidates[0].get("content", {})
            parts = content_obj.get("parts", [])
            if not parts:
                raise ValueError(f"No content parts in Gemini response: {candidates[0]}")
                
            content = parts[0].get("text", "")
            return UniversalMessage(content)
            
        except Exception as e:
            logger.error(f"Gemini request failed: {e}")
            raise e

    def _create_openrouter(self, model: str, messages: List[Dict[str, str]],
                           max_tokens: int, temperature: float, system: str):
        api_key = self.api_key or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not configured")

        if not model or "/" not in model:
            model = os.getenv("OPENROUTER_MODEL", "openrouter/auto")

        openrouter_messages = list(messages)
        if system:
            openrouter_messages = [{"role": "system", "content": system}] + openrouter_messages

        payload = {
            "model": model,
            "messages": openrouter_messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        # Add identifying headers for better OpenRouter citizenship & stability
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:3000", # Client URL
            "X-Title": "Obsidian RAG" # App Name
        }

        retries = 3
        for attempt in range(retries):
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60
                )

                if response.status_code == 200:
                    data = response.json()
                    choices = data.get("choices", [])
                    if not choices:
                        raise ValueError("No choices returned from OpenRouter")

                    message = choices[0].get("message", {})
                    content = message.get("content", "")
                    return UniversalMessage(content)
                elif response.status_code >= 500:
                    # Retry on server errors
                    logger.warning(f"OpenRouter 5xx error (attempt {attempt+1}/{retries}): {response.text}")
                    if attempt < retries - 1:
                        import time
                        time.sleep(1 * (attempt + 1))
                        continue
                    else:
                        raise ValueError(f"OpenRouter API Error {response.status_code}: {response.text}")
                else:
                    # Don't retry client errors (4xx)
                    error_msg = f"OpenRouter API Error {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)

            except Exception as e:
                logger.error(f"OpenRouter request failed (attempt {attempt+1}/{retries}): {e}")
                if attempt < retries - 1:
                    import time
                    time.sleep(1)
                    continue
                raise e

    def _create_openai(self, model: str, messages: List[Dict[str, str]],
                       max_tokens: int, temperature: float, system: str):
        api_key = self.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured")

        if not model or "gemini" in model.lower() or "claude" in model.lower():
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        openai_messages = list(messages)
        if system:
            openai_messages = [{"role": "system", "content": system}] + openai_messages

        token_param = "max_tokens"
        restrict_temperature = False
        if model:
            model_lower = model.lower()
            if model_lower.startswith(("gpt-5", "o1", "o3")):
                token_param = "max_completion_tokens"
                restrict_temperature = True

        timeout = float(os.getenv("OPENAI_TIMEOUT", "60"))
        payload = {
            "model": model,
            "messages": openai_messages,
            token_param: max_tokens
        }
        if not restrict_temperature:
            payload["temperature"] = temperature

        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=timeout
            )

            if response.status_code != 200:
                error_msg = f"OpenAI API Error {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise ValueError(error_msg)

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                error_detail = data.get("error", {}).get("message", "No choices returned from OpenAI")
                raise ValueError(error_detail)

            message = choices[0].get("message", {})
            content = message.get("content")
            if content is None:
                content = message.get("refusal")
            if content is None:
                content = choices[0].get("text")
            if content is None:
                content = choices[0].get("delta", {}).get("content")

            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, dict):
                        if "text" in part:
                            parts.append(str(part["text"]))
                        continue
                    parts.append(str(part))
                content = "".join(parts)

            if content is None or content == "":
                finish_reason = choices[0].get("finish_reason")
                reason_note = f" (finish_reason={finish_reason})" if finish_reason else ""
                raise ValueError(f"Empty response from OpenAI{reason_note}")

            return UniversalMessage(str(content))
        except Exception as e:
            logger.error(f"OpenAI request failed: {e}")
            raise e
    def _create_ollama(self, model: str, messages: List[Dict[str, str]],
                       max_tokens: int, temperature: float, system: str):
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        if "host.docker.internal" in ollama_host:
             # If running outside docker but env var is set for docker, try localhost fallback
             pass # Python request library handles DNS, but usually better to stick to what's given

        if not model or "claude" in model or "gpt" in model:
            # Fallback to a common default or env var
            model = os.getenv("OLLAMA_MODEL", "mistral") # Default fallback

        # Ollama API structure: POST /api/chat
        # Messages format: same as OpenAI
        
        ollama_messages = list(messages)
        # DeepSeek R1 and some other models degrade with system prompts, but most support it.
        # Check for deepseek-r1 specifically to avoid system prompt if desired, 
        # but generally Ollama handles system messages by converting them to the model template.
        is_deepseek_r1 = "deepseek-r1" in model.lower()
        
        if system and not is_deepseek_r1:
            ollama_messages = [{"role": "system", "content": system}] + ollama_messages
        elif system and is_deepseek_r1:
            # For DeepSeek R1, prepend system prompt to first user message or just ignore (per user preference)
            # We'll prepend to first message to keep context
            if ollama_messages:
                 ollama_messages[0]["content"] = f"{system}\n\n{ollama_messages[0]['content']}"

        payload = {
            "model": model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": 32768, # Ensure large context for RAG
                "num_predict": max_tokens
            }
        }

        try:
            # Ensure host has protocol
            if not ollama_host.startswith("http"):
                ollama_host = f"http://{ollama_host}"
                
            url = f"{ollama_host}/api/chat"
            response = requests.post(url, json=payload, timeout=120)
            
            if response.status_code != 200:
                 error_msg = f"Ollama API Error {response.status_code}: {response.text}"
                 logger.error(error_msg)
                 raise ValueError(error_msg)

            data = response.json()
            message = data.get("message", {})
            content = message.get("content", "")
            
            # DeepSeek R1 <think> block handling
            # If the model emits thought blocks, we might want to keep them or strip them.
            # For "Deep Thinking" agent, keeping them in the logs/trace but returning clean answer is tricky.
            # For now, we return full content. The Synthesizer might see extra text, but it usually handles it.
            
            return UniversalMessage(content)

        except Exception as e:
            logger.error(f"Ollama request failed: {e}")
            raise e
