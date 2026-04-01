import { NextResponse } from 'next/server';

const resolveVaultRoot = (): string => process.env.OBSIDIAN_VAULT_PATH || '/app/vault';

export async function GET() {
  const vaultRoot = resolveVaultRoot();
  const vaultName = vaultRoot.split('/').filter(Boolean).pop() || 'Vault';
  const config = {
    keys: {
      gemini: !!process.env.GEMINI_API_KEY,
      anthropic: !!process.env.ANTHROPIC_API_KEY,
      openai: !!process.env.OPENAI_API_KEY,
      lmstudio: !!(process.env.LMSTUDIO_BASE_URL || process.env.LMSTUDIO_MODEL || process.env.LLM_MODEL_PATH),
    },
    models: {
      ollama: process.env.OLLAMA_MODEL || 'mistral',
      openrouter: process.env.OPENROUTER_MODEL || 'google/gemini-2.0-flash-exp:free',
      chatgpt: process.env.OPENAI_MODEL || 'gpt-4o',
      gemini: process.env.GEMINI_MODEL || 'gemini-1.5-pro',
      claude: process.env.CLAUDE_MODEL || 'claude-3-5-sonnet-latest',
      lmstudio: process.env.LMSTUDIO_MODEL || process.env.LLM_MODEL_PATH || 'local-model'
    },
    vault: {
      name: vaultName,
      root: vaultRoot,
    }
  };

  return NextResponse.json(config);
}
