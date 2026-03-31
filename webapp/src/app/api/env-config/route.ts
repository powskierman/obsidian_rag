import { NextResponse } from 'next/server';

export async function GET() {
  const config = {
    runtimeProfile: process.env.NEXT_PUBLIC_RUNTIME_PROFILE || process.env.OBSIDIAN_RAG_PROFILE || 'canmore',
    defaultProvider: process.env.NEXT_PUBLIC_DEFAULT_LLM_PROVIDER || process.env.DEFAULT_LLM_PROVIDER || 'openrouter',
    keys: {
      gemini: !!process.env.GEMINI_API_KEY,
      anthropic: !!process.env.ANTHROPIC_API_KEY,
      openai: !!process.env.OPENAI_API_KEY,
      lmstudio: !!(process.env.LMSTUDIO_BASE_URL || process.env.LMSTUDIO_MODEL || process.env.LLM_MODEL_PATH),
    },
    models: {
      ollama: process.env.OLLAMA_MODEL || 'qwen3.5:9b',
      openrouter: process.env.OPENROUTER_MODEL || 'google/gemini-2.0-flash-exp:free',
      chatgpt: process.env.OPENAI_MODEL || 'gpt-4o',
      gemini: process.env.GEMINI_MODEL || 'gemini-1.5-pro',
      claude: process.env.CLAUDE_MODEL || 'claude-3-5-sonnet-latest',
      lmstudio: process.env.LMSTUDIO_MODEL || process.env.LLM_MODEL_PATH || 'local-model'
    }
  };

  return NextResponse.json(config);
}
