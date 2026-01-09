#!/usr/bin/env python3
"""
Universal LLM Client wrapper for Deep Thinking Agent.
Supports Anthropic (Claude), Google (Gemini), and OpenRouter APIs with a unified interface.
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
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

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

        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=60
            )

            if response.status_code != 200:
                error_msg = f"OpenRouter API Error {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise ValueError(error_msg)

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("No choices returned from OpenRouter")

            message = choices[0].get("message", {})
            content = message.get("content", "")
            return UniversalMessage(content)
        except Exception as e:
            logger.error(f"OpenRouter request failed: {e}")
            raise e
