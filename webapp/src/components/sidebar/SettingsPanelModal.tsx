import { useEffect, useState } from 'react';
import { useApp } from '../../context/AppContext';
import { api } from '../../lib/api';

interface SettingsPanelModalProps {
  onClose: () => void;
}

export default function SettingsPanelModal({ onClose }: SettingsPanelModalProps) {
  const { settings, updateSettings } = useApp();
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(true);

  useEffect(() => {
    const loadModels = async () => {
      setIsLoadingModels(true);
      try {
        const models = await api.getOllamaModels();
        setAvailableModels(models);
      } catch (error) {
        console.error('Failed to load models:', error);
      } finally {
        setIsLoadingModels(false);
      }
    };
    loadModels();
  }, []);

  const handleModelChange = (model: string) => {
    updateSettings({ ...settings, model });
  };

  const handleSourcesChange = (sources: number) => {
    updateSettings({ ...settings, sources });
  };

  const handleTemperatureChange = (temperature: number) => {
    updateSettings({ ...settings, temperature });
  };

  const handleToggle = (key: 'showSources' | 'enhancedSearch') => {
    updateSettings({ ...settings, [key]: !settings[key] });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-[#1C1C1E] rounded-2xl border border-[#2C2C2E] p-6 w-[450px] max-w-[90vw] max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <span className="text-2xl">⚙️</span>
            <h2 className="text-xl font-bold text-white">Settings</h2>
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

        <p className="text-sm text-white/60 mb-6">Configure search and response parameters</p>

        <div className="space-y-6">
          {/* LLM Provider Selection */}
          <div>
            <label className="block text-sm font-medium text-white mb-3">
              LLM Provider
            </label>
            <div className="bg-[#2C2C2E] p-1 rounded-xl flex border border-[#3C3C3E]">
              {['ollama', 'gemini', 'claude'].map((provider) => (
                <button
                  key={provider}
                  onClick={() => useApp().setLLMProvider(provider as any)}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-all capitalize ${useApp().llmProvider === provider
                    ? 'bg-[#0A84FF] text-white shadow-lg'
                    : 'text-white/40 hover:text-white/60 hover:bg-white/5'
                    }`}
                >
                  {provider}
                </button>
              ))}
            </div>
          </div>

          {/* Model Selection (Conditional) */}
          {useApp().llmProvider === 'ollama' && (
            <div>
              <label className="block text-sm font-medium text-white mb-2">
                Models
              </label>
              <select
                value={settings.model}
                onChange={(e) => handleModelChange(e.target.value)}
                disabled={isLoadingModels}
                className="w-full bg-[#2C2C2E] text-white border border-[#3C3C3E] rounded-lg px-4 py-2 focus:outline-none focus:border-[#0A84FF] disabled:opacity-50 appearance-none cursor-pointer"
              >
                {isLoadingModels ? (
                  <option>Loading models...</option>
                ) : availableModels.length > 0 ? (
                  availableModels.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))
                ) : (
                  <option>No models available</option>
                )}
              </select>
              <p className="text-xs text-white/40 mt-1.5 flex items-center gap-1.5">
                <span className="w-1 h-1 rounded-full bg-[#0A84FF]" />
                Choose the local Ollama model
              </p>
            </div>
          )}

          {/* Number of Sources */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-white">
                Number of Sources
              </label>
              <span className="text-sm font-mono text-[#0A84FF]">{settings.sources}</span>
            </div>
            <input
              type="range"
              min="1"
              max="50"
              value={settings.sources}
              onChange={(e) => handleSourcesChange(Number(e.target.value))}
              className="w-full h-2 bg-[#2C2C2E] rounded-lg appearance-none cursor-pointer slider"
              style={{
                background: `linear-gradient(to right, #0A84FF 0%, #0A84FF ${(settings.sources / 50) * 100}%, #2C2C2E ${(settings.sources / 50) * 100}%, #2C2C2E 100%)`
              }}
            />
            <div className="flex justify-between text-xs text-white/40 mt-1">
              <span>1</span>
              <span>50</span>
            </div>
            <p className="text-xs text-white/40 mt-1">Number of context chunks to retrieve</p>
          </div>

          {/* Temperature */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-white">
                Temperature
              </label>
              <span className="text-sm font-mono text-[#0A84FF]">{settings.temperature.toFixed(1)}</span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={settings.temperature}
              onChange={(e) => handleTemperatureChange(Number(e.target.value))}
              className="w-full h-2 bg-[#2C2C2E] rounded-lg appearance-none cursor-pointer slider"
              style={{
                background: `linear-gradient(to right, #0A84FF 0%, #0A84FF ${settings.temperature * 100}%, #2C2C2E ${settings.temperature * 100}%, #2C2C2E 100%)`
              }}
            />
            <div className="flex justify-between text-xs text-white/40 mt-1">
              <span>0.0 (Focused)</span>
              <span>1.0 (Creative)</span>
            </div>
            <p className="text-xs text-white/40 mt-1">Controls randomness in responses</p>
          </div>

          {/* Show Sources Toggle */}
          <div className="flex items-center justify-between p-3 bg-[#2C2C2E] rounded-lg border border-[#3C3C3E]">
            <div>
              <div className="text-sm font-medium text-white">Show Sources</div>
              <div className="text-xs text-white/40 mt-1">Display source documents with answers</div>
            </div>
            <button
              onClick={() => handleToggle('showSources')}
              className={`relative w-12 h-6 rounded-full transition-colors ${settings.showSources ? 'bg-[#0A84FF]' : 'bg-[#3C3C3E]'
                }`}
            >
              <div
                className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${settings.showSources ? 'translate-x-6' : 'translate-x-0'
                  }`}
              />
            </button>
          </div>

          {/* Enhanced Search Toggle */}
          <div className="flex items-center justify-between p-3 bg-[#2C2C2E] rounded-lg border border-[#3C3C3E]">
            <div>
              <div className="text-sm font-medium text-white">Enhanced Search</div>
              <div className="text-xs text-white/40 mt-1">Enable re-ranking and deduplication</div>
            </div>
            <button
              onClick={() => handleToggle('enhancedSearch')}
              className={`relative w-12 h-6 rounded-full transition-colors ${settings.enhancedSearch ? 'bg-[#0A84FF]' : 'bg-[#3C3C3E]'
                }`}
            >
              <div
                className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${settings.enhancedSearch ? 'translate-x-6' : 'translate-x-0'
                  }`}
              />
            </button>
          </div>

          {/* Deep Thinking Toggle */}
          <div className="flex items-center justify-between p-3 bg-[#2C2C2E] rounded-lg border border-[#3C3C3E]">
            <div>
              <div className="text-sm font-medium text-white">Deep Thinking</div>
              <div className="text-xs text-white/40 mt-1">Enable agentic reasoning for complex tasks</div>
            </div>
            <button
              onClick={() => updateSettings({ ...settings, deepThinking: !settings.deepThinking })}
              className={`relative w-12 h-6 rounded-full transition-colors ${settings.deepThinking ? 'bg-[#0A84FF]' : 'bg-[#3C3C3E]'
                }`}
            >
              <div
                className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${settings.deepThinking ? 'translate-x-6' : 'translate-x-0'
                  }`}
              />
            </button>
          </div>
        </div>

        <div className="mt-6 pt-4 border-t border-[#2C2C2E]">
          <button
            onClick={onClose}
            className="w-full bg-[#0A84FF] hover:bg-[#0077ED] text-white font-medium py-2 px-4 rounded-lg transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
