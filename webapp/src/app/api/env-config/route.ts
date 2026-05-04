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
      openrouter: !!process.env.OPENROUTER_API_KEY,
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
    pdfTree: {
      enabled: ['1', 'true', 'yes', 'on'].includes((process.env.PDF_TREE_RETRIEVAL_ENABLED || 'false').toLowerCase()),
      provider: process.env.PDF_TREE_PROVIDER || 'ollama',
      configured: Boolean(process.env.PDF_TREE_MODEL || process.env.OLLAMA_MODEL || process.env.LMSTUDIO_MODEL || process.env.OPENROUTER_API_KEY),
      reachable: false,
      hosted: process.env.PDF_TREE_PROVIDER === 'openrouter',
      model: process.env.PDF_TREE_MODEL || process.env.OLLAMA_MODEL || process.env.LMSTUDIO_MODEL || process.env.OPENROUTER_MODEL || 'llama3.1:8b',
      baseUrl: process.env.OLLAMA_BASE_URL || process.env.OLLAMA_HOST || process.env.LMSTUDIO_BASE_URL || process.env.OPENROUTER_BASE_URL || '',
      models: [],
      error: null,
    },
    vault: {
      name: vaultName,
      root: vaultRoot,
    }
  };

  return NextResponse.json(config);
}
