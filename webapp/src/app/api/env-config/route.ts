import { NextResponse } from 'next/server';

export async function GET() {
  const config = {
    keys: {
      gemini: !!process.env.GEMINI_API_KEY,
      anthropic: !!process.env.ANTHROPIC_API_KEY,
      openai: !!process.env.OPENAI_API_KEY,
    },
    models: {
      ollama: process.env.OLLAMA_MODEL || 'mistral',
      openrouter: process.env.OPENROUTER_MODEL || 'google/gemini-2.0-flash-exp:free',
      chatgpt: process.env.OPENAI_MODEL || 'gpt-4o',
      gemini: process.env.GEMINI_MODEL || 'gemini-1.5-pro',
      claude: process.env.CLAUDE_MODEL || 'claude-3-5-sonnet-latest'
    }
  };

  return NextResponse.json(config);
}
