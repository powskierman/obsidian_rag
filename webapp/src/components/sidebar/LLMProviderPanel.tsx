import { useEffect, useState } from 'react';
import { LLMProvider } from '../../lib/types';
import { api } from '../../lib/api';

interface LLMProviderPanelProps {
  currentProvider: LLMProvider;
  onSelect: (provider: LLMProvider) => void;
  onClose: () => void;
}

const llmProviders = [
  {
    id: 'ollama' as LLMProvider,
    label: 'Ollama',
    cost: 'Free',
    icon: '🦙',
    requiresApiKey: false
  },
  {
    id: 'gemini' as LLMProvider,
    label: 'Gemini Pro',
    cost: '$',
    icon: '✨',
    requiresApiKey: true,
    apiKeyEnvVar: 'GEMINI_API_KEY'
  },
  {
    id: 'claude' as LLMProvider,
    label: 'Claude API',
    cost: '$',
    icon: '🤖',
    requiresApiKey: true,
    apiKeyEnvVar: 'ANTHROPIC_API_KEY'
  },
  {
    id: 'openrouter' as LLMProvider,
    label: 'OpenRouter',
    cost: '$',
    icon: '🧭',
    requiresApiKey: true,
    apiKeyEnvVar: 'OPENROUTER_API_KEY'
  }
];

export default function LLMProviderPanel({ currentProvider, onSelect, onClose }: LLMProviderPanelProps) {
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

  const handleSelect = (provider: LLMProvider) => {
    onSelect(provider);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-[#1C1C1E] rounded-2xl border border-[#2C2C2E] p-6 w-[400px] max-w-[90vw]" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🤖</span>
            <h2 className="text-xl font-bold text-white">LLM Provider</h2>
          </div>
          <button
            onClick={onClose}
            className="text-white/40 hover:text-white transition-colors"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <p className="text-sm text-white/60 mb-4">Choose your LLM provider:</p>

        <div className="space-y-2">
          {llmProviders.map((provider) => {
            const hasKey = provider.id === 'gemini'
              ? apiKeys.gemini
              : provider.id === 'claude'
                ? apiKeys.anthropic
                : true;
            const showWarning = provider.requiresApiKey && !hasKey;

            return (
              <label
                key={provider.id}
                className={`flex items-center gap-3 p-4 rounded-xl border cursor-pointer transition-all ${
                  currentProvider === provider.id
                    ? 'bg-[#0A84FF]/10 border-[#0A84FF]'
                    : 'bg-[#1C1C1E] border-[#2C2C2E] hover:border-white/20'
                }`}
              >
                <input
                  type="radio"
                  name="llmProvider"
                  value={provider.id}
                  checked={currentProvider === provider.id}
                  onChange={() => handleSelect(provider.id)}
                  className="w-5 h-5 text-[#0A84FF] bg-transparent border-2 border-white/20 focus:ring-2 focus:ring-[#0A84FF] cursor-pointer"
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-lg">{provider.icon}</span>
                    <span className="text-white font-medium">
                      {provider.label} ({provider.cost})
                    </span>
                  </div>
                  {provider.id === 'openrouter' && currentProvider === provider.id && (
                    <p className="text-xs text-white/50 flex items-center gap-1 mt-1">
                      <span>🔑</span>
                      <span>Set OPENROUTER_API_KEY</span>
                    </p>
                  )}
                  {showWarning && provider.id !== 'openrouter' && (
                    <p className="text-xs text-yellow-500/70 flex items-center gap-1 mt-1">
                      <span>⚠️</span>
                      <span>API key required</span>
                    </p>
                  )}
                  {!showWarning && provider.requiresApiKey && currentProvider === provider.id && (
                    <p className="text-xs text-green-500/70 flex items-center gap-1 mt-1">
                      <span>✓</span>
                      <span>API key configured</span>
                    </p>
                  )}
                </div>
              </label>
            );
          })}
        </div>
      </div>
    </div>
  );
}
