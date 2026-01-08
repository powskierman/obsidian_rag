import { useApp } from '../../context/AppContext';
import { LLMProvider } from '../../lib/types';
import { api } from '../../lib/api';
import { useEffect, useState } from 'react';

const llmProviders = [
  {
    id: 'ollama' as LLMProvider,
    label: 'Ollama',
    cost: 'Free',
    requiresApiKey: false
  },
  {
    id: 'gemini' as LLMProvider,
    label: 'Gemini Pro',
    cost: '$',
    requiresApiKey: true,
    apiKeyEnvVar: 'GEMINI_API_KEY'
  },
  {
    id: 'claude' as LLMProvider,
    label: 'Claude API',
    cost: '$',
    requiresApiKey: true,
    apiKeyEnvVar: 'ANTHROPIC_API_KEY'
  },
  {
    id: 'openrouter' as LLMProvider,
    label: 'OpenRouter',
    cost: '$',
    requiresApiKey: true,
    apiKeyEnvVar: 'OPENROUTER_API_KEY'
  }
];

export default function LLMProviderSelector() {
  const { llmProvider, setLLMProvider } = useApp();
  const [apiKeys, setApiKeys] = useState<{ gemini: boolean; anthropic: boolean }>({
    gemini: false,
    anthropic: false
  });

  useEffect(() => {
    const checkKeys = async () => {
      const keys = await api.checkApiKeys();
      setApiKeys(keys);
    };
    checkKeys();
  }, []);

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <span className="text-lg">🤖</span>
          <label className="text-xs font-semibold text-white/40 uppercase tracking-wider">
            LLM Provider
          </label>
        </div>
        <p className="text-xs text-white/50 pl-7">Choose LLM:</p>
      </div>

      <div className="space-y-2">
        {llmProviders.map((provider) => (
          <button
            key={provider.id}
            onClick={() => setLLMProvider(provider.id)}
            className={`w-full flex items-center justify-between p-3 rounded-xl border transition-all text-left ${
              llmProvider === provider.id
                ? 'bg-[#0A84FF]/10 border-[#0A84FF] text-white'
                : 'bg-[#1C1C1E] border-[#2C2C2E] text-white/60 hover:border-white/20'
            }`}
          >
            <div className="flex-1">
              <div className="text-sm font-medium">
                {provider.label} ({provider.cost})
              </div>
              {provider.requiresApiKey && (() => {
                const hasKey = provider.id === 'gemini'
                  ? apiKeys.gemini
                  : provider.id === 'claude'
                    ? apiKeys.anthropic
                    : true;
                if (!hasKey && provider.id !== 'openrouter') {
                  return (
                    <div className="text-xs text-yellow-500/70 mt-1 flex items-center gap-1">
                      <span>⚠️</span>
                      <span>API key required</span>
                    </div>
                  );
                } else if (provider.id === 'openrouter' && llmProvider === provider.id) {
                  return (
                    <div className="text-xs text-white/50 mt-1 flex items-center gap-1">
                      <span>🔑</span>
                      <span>Set OPENROUTER_API_KEY</span>
                    </div>
                  );
                } else if (llmProvider === provider.id) {
                  return (
                    <div className="text-xs text-green-500/70 mt-1 flex items-center gap-1">
                      <span>✓</span>
                      <span>API key configured</span>
                    </div>
                  );
                }
                return null;
              })()}
            </div>
            {llmProvider === provider.id && (
              <div className="w-2 h-2 rounded-full bg-[#0A84FF]" />
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
