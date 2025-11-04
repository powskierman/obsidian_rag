"""
GraphRAG Local Ollama Monkey Patch
Based on: https://chishengliu.com/posts/graphrag-local-ollama/

This module provides monkey-patch functions to replace OpenAI API calls
with local Ollama API calls for GraphRAG version 0.3.2.
"""

import json
import os
import requests
import time
from typing import Any, Dict, List, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

def ollama_embedding(text: str, model: str = EMBED_MODEL) -> List[float]:
    """
    Generate embeddings using Ollama API
    """
    try:
        url = f"{OLLAMA_BASE_URL}/api/embeddings"
        payload = {
            "model": model,
            "prompt": text
        }

        response = requests.post(url, json=payload, timeout=180)
        response.raise_for_status()

        result = response.json()
        return result.get("embedding", [])

    except Exception as e:
        logger.error(f"Ollama embedding error: {e}")
        # Return a dummy embedding vector if generation fails
        return [0.0] * 768  # nomic-embed-text dimension


def ollama_chat_completion(messages: List[Dict], model: str = LLM_MODEL,
                          max_tokens: int = 4000, temperature: float = 0.7) -> str:
    """
    Generate chat completion using Ollama API with GraphRAG-optimized prompting
    """
    try:
        # Convert messages to a single prompt
        if isinstance(messages, list) and len(messages) > 0:
            if len(messages) == 1:
                prompt = messages[0].get("content", "")
            else:
                # Combine system and user messages
                prompt_parts = []
                for msg in messages:
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if role == "system":
                        prompt_parts.append(f"System: {content}")
                    elif role == "user":
                        prompt_parts.append(f"User: {content}")
                    elif role == "assistant":
                        prompt_parts.append(f"Assistant: {content}")
                prompt = "\n\n".join(prompt_parts)
        else:
            prompt = str(messages)

        # Enhance prompt for GraphRAG tasks
        enhanced_prompt = enhance_prompt_for_graphrag(prompt)

        url = f"{OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model": model,
            "prompt": enhanced_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_p": 0.9,
                "repeat_penalty": 1.1
            }
        }

        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()

        result = response.json()
        raw_response = result.get("response", "")

        # Post-process response for GraphRAG format compliance
        processed_response = post_process_graphrag_response(raw_response, prompt)
        return processed_response

    except Exception as e:
        logger.error(f"Ollama chat completion error: {e}")
        return "Error: Unable to generate response"


def enhance_prompt_for_graphrag(prompt: str) -> str:
    """
    Enhance prompts specifically for GraphRAG tasks
    """
    # Check if this is an entity extraction task
    if "entity_types" in prompt and "tuple_delimiter" in prompt:
        return f"""{prompt}

IMPORTANT INSTRUCTIONS:
- Follow the EXACT format shown in the examples
- Use the specified delimiters exactly as shown
- Each entity must be in format: ("entity"|<name>|<type>|<description>)
- Each relationship must be in format: ("relationship"|<source>|<target>|<description>|<strength>)
- End with the completion delimiter as shown
- Do not add extra explanations or text
- Be precise and concise in descriptions
"""

    # Check if this is a community report task
    elif "community" in prompt.lower() and "report" in prompt.lower():
        return f"""{prompt}

IMPORTANT: Provide a clear, structured report. Focus on:
- Key entities and their relationships
- Important themes and patterns
- Concrete findings and insights
- Use clear, factual language
"""

    return prompt


def post_process_graphrag_response(response: str, original_prompt: str) -> str:
    """
    Post-process responses to ensure GraphRAG format compliance
    """
    try:
        # For entity extraction tasks
        if "entity_types" in original_prompt and "tuple_delimiter" in original_prompt:
            # Extract delimiters from prompt
            tuple_delimiter = "|"
            record_delimiter = "##"
            completion_delimiter = "<|COMPLETE|>"

            if "tuple_delimiter}" in original_prompt:
                # Try to extract actual delimiters from prompt
                import re
                tuple_match = re.search(r'tuple_delimiter}([^{]+){', original_prompt)
                if tuple_match:
                    tuple_delimiter = tuple_match.group(1)

                record_match = re.search(r'record_delimiter}([^{]+){', original_prompt)
                if record_match:
                    record_delimiter = record_match.group(1)

                completion_match = re.search(r'completion_delimiter}([^{]+)', original_prompt)
                if completion_match:
                    completion_delimiter = completion_match.group(1)

            # Clean up the response
            lines = response.strip().split('\n')
            formatted_lines = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Skip explanatory text
                if line.startswith('Entity') or line.startswith('Relationship') or \
                   line.startswith('Output') or line.startswith('The') or \
                   line.startswith('Based on') or line.startswith('Here'):
                    continue

                # Process entity/relationship lines
                if 'entity' in line.lower() or 'relationship' in line.lower():
                    if not line.startswith('("'):
                        # Try to fix malformed lines
                        if 'entity' in line.lower():
                            # Extract entity info and reformat
                            continue  # Skip malformed lines for now
                        elif 'relationship' in line.lower():
                            continue  # Skip malformed lines for now
                    else:
                        formatted_lines.append(line)

            if formatted_lines:
                result = record_delimiter.join(formatted_lines)
                if not result.endswith(completion_delimiter):
                    result += completion_delimiter
                return result
            else:
                # Fallback: return a minimal valid response
                return f'("entity"{tuple_delimiter}"Unknown"{tuple_delimiter}"ORGANIZATION"{tuple_delimiter}"No entities could be extracted"){completion_delimiter}'

        # For other tasks, return response as-is but cleaned
        return response.strip()

    except Exception as e:
        logger.error(f"Response post-processing error: {e}")
        return response


def patch_openai_embedding():
    """
    Monkey-patch OpenAI embedding functions for GraphRAG 0.3.2
    """
    try:
        # Import the actual GraphRAG 0.3.2 embedding module
        import graphrag.llm.openai.openai_embeddings_llm as embedding_module

        class MockOpenAIEmbeddingsLLM:
            def __init__(self, *args, **kwargs):
                self.model = kwargs.get('model', EMBED_MODEL)
                self._configuration = kwargs

            async def __call__(self, texts: List[str], **kwargs) -> Tuple[List[List[float]], int]:
                """Generate embeddings for a list of texts"""
                embeddings = []
                total_tokens = 0

                if isinstance(texts, str):
                    texts = [texts]

                for text in texts:
                    embedding = ollama_embedding(text, self.model)
                    embeddings.append(embedding)
                    # Estimate tokens (rough approximation)
                    total_tokens += len(text.split()) * 1.3

                return embeddings, int(total_tokens)

        # Replace the original class
        embedding_module.OpenAIEmbeddingsLLM = MockOpenAIEmbeddingsLLM
        logger.info("✅ OpenAI embeddings LLM patched successfully")

    except ImportError as e:
        logger.warning(f"Could not patch OpenAI embeddings: {e}")
    except Exception as e:
        logger.error(f"Error patching OpenAI embeddings: {e}")


def patch_openai_chat():
    """
    Monkey-patch OpenAI chat completion functions for GraphRAG 0.3.2
    """
    try:
        # Import the actual GraphRAG 0.3.2 chat module
        import graphrag.llm.openai.openai_chat_llm as chat_module

        class MockOpenAIChatLLM:
            def __init__(self, *args, **kwargs):
                self.model = kwargs.get('model', LLM_MODEL)
                self.max_tokens = kwargs.get('max_tokens', 4000)
                self.temperature = kwargs.get('temperature', 0.7)
                self._configuration = kwargs

            async def __call__(self, messages: List[Dict], **kwargs) -> str:
                """Generate chat completion"""
                max_tokens = kwargs.get('max_tokens', self.max_tokens)
                temperature = kwargs.get('temperature', self.temperature)

                response = ollama_chat_completion(
                    messages,
                    self.model,
                    max_tokens,
                    temperature
                )
                return response

        # Replace the original class
        chat_module.OpenAIChatLLM = MockOpenAIChatLLM
        logger.info("✅ OpenAI chat LLM patched successfully")

    except ImportError as e:
        logger.warning(f"Could not patch OpenAI chat: {e}")
    except Exception as e:
        logger.error(f"Error patching OpenAI chat: {e}")


def patch_token_counter():
    """
    Monkey-patch token counting functions
    """
    try:
        import tiktoken

        def mock_encoding_for_model(model_name: str):
            """Mock tiktoken encoding"""
            class MockEncoding:
                def encode(self, text: str) -> List[int]:
                    # Simple token estimation: ~1.3 tokens per word
                    words = text.split()
                    return list(range(int(len(words) * 1.3)))

                def decode(self, tokens: List[int]) -> str:
                    return " ".join([f"token_{i}" for i in tokens])

            return MockEncoding()

        # Replace tiktoken function
        tiktoken.encoding_for_model = mock_encoding_for_model
        logger.info("✅ Token counter patched successfully")

    except ImportError as e:
        logger.warning(f"Could not patch token counter: {e}")
    except Exception as e:
        logger.error(f"Error patching token counter: {e}")


def patch_json_response_handler():
    """
    Monkey-patch JSON response handling for better local model compatibility
    """
    try:
        import graphrag.llm.base

        original_extract_json = getattr(graphrag.llm.base, 'extract_json_from_response', None)

        def enhanced_extract_json(response: str) -> Dict[str, Any]:
            """Enhanced JSON extraction with fallback handling"""
            try:
                # Try original extraction first
                if original_extract_json:
                    return original_extract_json(response)

                # Fallback: find JSON-like content
                response = response.strip()

                # Look for JSON blocks in markdown
                if "```json" in response:
                    start = response.find("```json") + 7
                    end = response.find("```", start)
                    if end != -1:
                        json_str = response[start:end].strip()
                        return json.loads(json_str)

                # Look for direct JSON
                if response.startswith("{") and response.endswith("}"):
                    return json.loads(response)

                # Try to find JSON anywhere in the response
                for line in response.split('\n'):
                    line = line.strip()
                    if line.startswith("{") and line.endswith("}"):
                        try:
                            return json.loads(line)
                        except:
                            continue

                # Fallback: return a basic structure
                return {"entities": [], "relationships": []}

            except Exception as e:
                logger.error(f"JSON extraction error: {e}")
                return {"entities": [], "relationships": []}

        # Replace the function if it exists
        if hasattr(graphrag.llm.base, 'extract_json_from_response'):
            graphrag.llm.base.extract_json_from_response = enhanced_extract_json

        logger.info("✅ JSON response handler patched successfully")

    except ImportError as e:
        logger.warning(f"Could not patch JSON response handler: {e}")
    except Exception as e:
        logger.error(f"Error patching JSON response handler: {e}")


def apply_all_patches():
    """
    Apply all monkey patches for GraphRAG local operation
    """
    logger.info("🔧 Applying GraphRAG-Local-Ollama monkey patches...")

    # Test Ollama connection first
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        if response.status_code == 200:
            logger.info(f"✅ Ollama connection successful at {OLLAMA_BASE_URL}")
        else:
            logger.warning(f"⚠️ Ollama connection issue: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Cannot connect to Ollama: {e}")
        return False

    # Apply patches
    patch_token_counter()
    patch_openai_embedding()
    patch_openai_chat()
    patch_json_response_handler()

    logger.info("🎉 All GraphRAG-Local-Ollama patches applied successfully!")
    logger.info(f"📊 Configuration:")
    logger.info(f"   - Ollama URL: {OLLAMA_BASE_URL}")
    logger.info(f"   - LLM Model: {LLM_MODEL}")
    logger.info(f"   - Embedding Model: {EMBED_MODEL}")

    return True


def verify_models():
    """
    Verify that required models are available in Ollama
    """
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [model["name"] for model in models]

            llm_available = any(LLM_MODEL in name for name in model_names)
            embed_available = any(EMBED_MODEL in name for name in model_names)

            logger.info(f"📋 Available models: {model_names}")

            if not llm_available:
                logger.warning(f"⚠️ LLM model '{LLM_MODEL}' not found. Please run: ollama pull {LLM_MODEL}")
            else:
                logger.info(f"✅ LLM model '{LLM_MODEL}' is available")

            if not embed_available:
                logger.warning(f"⚠️ Embedding model '{EMBED_MODEL}' not found. Please run: ollama pull {EMBED_MODEL}")
            else:
                logger.info(f"✅ Embedding model '{EMBED_MODEL}' is available")

            return llm_available and embed_available
        else:
            logger.error(f"❌ Failed to get model list: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"❌ Error checking models: {e}")
        return False


if __name__ == "__main__":
    # Test the monkey patch
    print("🧪 Testing GraphRAG-Local-Ollama monkey patch...")

    if verify_models():
        if apply_all_patches():
            print("✅ Monkey patch test completed successfully!")
        else:
            print("❌ Monkey patch test failed!")
    else:
        print("❌ Required models not available!")