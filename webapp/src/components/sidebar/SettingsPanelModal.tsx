import { useCallback, useEffect, useRef, useState } from 'react';
import { useApp } from '../../context/AppContext';
import { api, PdfTreeProviderStatus } from '../../lib/api';
import { PdfTreeProvider } from '../../lib/types';

interface SettingsPanelModalProps {
  onClose: () => void;
}

export default function SettingsPanelModal({ onClose }: SettingsPanelModalProps) {
  const { settings, updateSettings, llmProvider, setLLMProvider } = useApp();
  const [availableModels, setAvailableModels] = useState<{ ollama: string[]; lmstudio: string[] }>({
    ollama: [],
    lmstudio: [],
  });
  const [installedLmStudioModels, setInstalledLmStudioModels] = useState<string[]>([]);
  const [isLmStudioReachable, setIsLmStudioReachable] = useState(false);
  const [pdfTreeStatus, setPdfTreeStatus] = useState<PdfTreeProviderStatus | null>(null);
  const [isLoadingModels, setIsLoadingModels] = useState(true);
  const enhancedDisabled = settings.deepThinking;

  // Indexing state
  type DbKey = 'vector' | 'graph' | 'lightrag' | 'pdf-tree' | 'mempalace';
  const DB_META: Record<DbKey, { label: string; desc: string }> = {
    vector:    { label: 'Vector DB',   desc: 'ChromaDB — semantic search' },
    graph:     { label: 'Graph DB',    desc: 'NetworkX — structural links' },
    lightrag:  { label: 'LightRAG',   desc: 'LightRAG — knowledge graph' },
    'pdf-tree': { label: 'PDF Tree', desc: 'Page-aware PDF retrieval index' },
    mempalace: { label: 'MemPalace',  desc: 'MemPalace — compressed memory' },
  };
  const [indexDatabases, setIndexDatabases] = useState<Set<DbKey>>(new Set(['vector']));
  const [indexMode, setIndexMode] = useState<'partial' | 'full'>('partial');
  const [indexRunning, setIndexRunning] = useState(false);
  const [indexOutput, setIndexOutput] = useState<string[]>([]);
  const [indexError, setIndexError] = useState<string | null>(null);
  const [indexExitCode, setIndexExitCode] = useState<number | null>(null);
  const [indexExpanded, setIndexExpanded] = useState(false);
  const outputRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const loadData = async () => {
      setIsLoadingModels(true);
      try {
        const [ollamaModels, lmstudioStatus, pdfTree] = await Promise.all([
          api.getOllamaModels(),
          api.getLmStudioModelStatus(),
          api.getPdfTreeProviderStatus(),
        ]);
        setAvailableModels({
          ollama: ollamaModels,
          lmstudio: lmstudioStatus.models,
        });
        setInstalledLmStudioModels(lmstudioStatus.installedModels);
        setIsLmStudioReachable(lmstudioStatus.reachable);
        setPdfTreeStatus(pdfTree);
      } catch (error) {
        console.error('Failed to load settings data:', error);
      } finally {
        setIsLoadingModels(false);
      }
    };
    loadData();
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const pollIndexStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/index');
      if (!res.ok) return;
      const data = await res.json();
      setIndexOutput(data.output ?? []);
      setIndexError(data.error ?? null);
      setIndexExitCode(data.exitCode ?? null);
      if (!data.running) {
        setIndexRunning(false);
        stopPolling();
      }
      if (outputRef.current) {
        outputRef.current.scrollTop = outputRef.current.scrollHeight;
      }
    } catch { /* ignore */ }
  }, [stopPolling]);

  const startIndexing = useCallback(async () => {
    setIndexRunning(true);
    setIndexOutput([]);
    setIndexError(null);
    setIndexExitCode(null);
    try {
      const res = await fetch('/api/index', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          databases: Array.from(indexDatabases),
          mode: indexMode,
          lightragIncludeExtensions: ['.md'],
        }),
      });
      if (res.status === 409) {
        setIndexError('An indexing job is already running.');
        setIndexRunning(false);
        return;
      }
      if (!res.ok) {
        const err = await res.text();
        setIndexError(`Failed to start: ${err}`);
        setIndexRunning(false);
        return;
      }
    } catch (e) {
      setIndexError(e instanceof Error ? e.message : 'Unknown error');
      setIndexRunning(false);
      return;
    }
    stopPolling();
    pollRef.current = setInterval(pollIndexStatus, 1500);
  }, [indexDatabases, indexMode, pollIndexStatus, stopPolling]);

  const handleStartIndexing = useCallback(() => {
    void startIndexing();
  }, [indexDatabases, startIndexing]);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const resetIndexJob = useCallback(async () => {
    stopPolling();
    await fetch('/api/index', { method: 'DELETE' });
    setIndexRunning(false);
    setIndexOutput([]);
    setIndexError(null);
    setIndexExitCode(null);
  }, [stopPolling]);

  const handleModelChange = (model: string) => {
    updateSettings({ ...settings, model });
  };

  const handleSourcesChange = (sources: number) => {
    updateSettings({ ...settings, sources });
  };

  const handleTemperatureChange = (temperature: number) => {
    updateSettings({ ...settings, temperature });
  };

  const handleToggle = (key: 'showSources' | 'enhancedSearch' | 'briefConceptIndex') => {
    if (key === 'enhancedSearch' && enhancedDisabled) {
      return;
    }
    updateSettings({ ...settings, [key]: !settings[key] });
  };

  const updatePdfTreeSettings = (patch: Partial<typeof settings.pdfTree>) => {
    updateSettings({
      pdfTree: {
        ...settings.pdfTree,
        ...patch,
      },
    });
  };

  const modelSelectValue = settings.model;
  const ensureCurrentModelOption = (models: string[]) => {
    const currentModel = settings.model.trim();
    if (!currentModel || models.includes(currentModel)) {
      return models;
    }
    return [currentModel, ...models];
  };
  const ollamaModelOptions = ensureCurrentModelOption(availableModels.ollama);
  const lmstudioDiscoveredModels = availableModels.lmstudio.length > 0
    ? availableModels.lmstudio
    : installedLmStudioModels;
  const lmstudioModelOptions = ensureCurrentModelOption(lmstudioDiscoveredModels);
  const isUsingInstalledLmStudioFallback = availableModels.lmstudio.length === 0 && installedLmStudioModels.length > 0;
  const pdfTreeModelOptions = (() => {
    if (settings.pdfTree.provider === 'ollama') return ensureCurrentModelOption(availableModels.ollama);
    if (settings.pdfTree.provider === 'lmstudio') return ensureCurrentModelOption(lmstudioModelOptions);
    if (pdfTreeStatus?.models?.length) return ensureCurrentModelOption(pdfTreeStatus.models);
    return ensureCurrentModelOption([]);
  })();

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

        <p className="text-sm text-white/60 mb-6">Configure search, web supplementation, and response parameters</p>

        <div className="space-y-6">
          {/* LLM Provider Selection */}
          <div>
            <label className="block text-sm font-medium text-white mb-3">
              LLM Provider
            </label>
            <div className="bg-[#2C2C2E] p-1 rounded-xl flex border border-[#3C3C3E]">
              {['ollama', 'gemini', 'claude', 'openrouter', 'chatgpt', 'lmstudio'].map((provider) => (
                <button
                  key={provider}
                  onClick={() => {
                    setLLMProvider(provider as any);
                  }}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-all capitalize ${llmProvider === provider
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
          {llmProvider === 'ollama' && (
            <div>
              <label className="block text-sm font-medium text-white mb-2">
                Models
              </label>
              <select
                value={modelSelectValue}
                onChange={(e) => handleModelChange(e.target.value)}
                disabled={isLoadingModels}
                className="w-full bg-[#2C2C2E] text-white border border-[#3C3C3E] rounded-lg px-4 py-2 focus:outline-none focus:border-[#0A84FF] disabled:opacity-50 appearance-none cursor-pointer"
              >
                {isLoadingModels ? (
                  <option>Loading models...</option>
                ) : ollamaModelOptions.length > 0 ? (
                  ollamaModelOptions.map((model) => (
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

          {llmProvider === 'openrouter' && (
            <div>
              <label className="block text-sm font-medium text-white mb-2">
                OpenRouter Model
              </label>
              <input
                value={settings.model}
                onChange={(e) => updateSettings({ ...settings, model: e.target.value })}
                placeholder="openrouter/auto or anthropic/claude-sonnet-4-5"
                className="w-full bg-[#2C2C2E] text-white border border-[#3C3C3E] rounded-lg px-4 py-2 focus:outline-none focus:border-[#0A84FF]"
              />
              <p className="text-xs text-white/40 mt-1.5">
                Use any OpenRouter model ID.
              </p>
            </div>
          )}

          {llmProvider === 'chatgpt' && (
            <div>
              <label className="block text-sm font-medium text-white mb-2">
                OpenAI Model
              </label>
              <input
                value={settings.model}
                onChange={(e) => updateSettings({ ...settings, model: e.target.value })}
                placeholder="gpt-4o-mini"
                className="w-full bg-[#2C2C2E] text-white border border-[#3C3C3E] rounded-lg px-4 py-2 focus:outline-none focus:border-[#0A84FF]"
              />
              <p className="text-xs text-white/40 mt-1.5">
                Use any OpenAI chat model ID.
              </p>
            </div>
          )}

          {llmProvider === 'lmstudio' && (
            <div>
              <label className="block text-sm font-medium text-white mb-2">
                LM Studio Model
              </label>
              {isLoadingModels || lmstudioModelOptions.length > 0 ? (
                <select
                  value={modelSelectValue}
                  onChange={(e) => handleModelChange(e.target.value)}
                  disabled={isLoadingModels}
                  className="w-full bg-[#2C2C2E] text-white border border-[#3C3C3E] rounded-lg px-4 py-2 focus:outline-none focus:border-[#0A84FF] disabled:opacity-50 appearance-none cursor-pointer"
                >
                  {isLoadingModels ? (
                    <option>Loading models...</option>
                  ) : (
                    lmstudioModelOptions.map((model) => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))
                  )}
                </select>
              ) : isLmStudioReachable ? (
                <input
                  value="No loaded models"
                  disabled
                  readOnly
                  className="w-full bg-[#2C2C2E] text-white/60 border border-[#3C3C3E] rounded-lg px-4 py-2 focus:outline-none disabled:opacity-100"
                />
              ) : (
                <input
                  value={settings.model}
                  onChange={(e) => updateSettings({ ...settings, model: e.target.value })}
                  placeholder="local-model"
                  className="w-full bg-[#2C2C2E] text-white border border-[#3C3C3E] rounded-lg px-4 py-2 focus:outline-none focus:border-[#0A84FF]"
                />
              )}
              <p className="text-xs text-white/40 mt-1.5">
                {lmstudioModelOptions.length > 0
                  ? isUsingInstalledLmStudioFallback
                    ? 'Choose an installed LM Studio model. Load it in LM Studio before sending a query.'
                    : 'Choose a model exposed by your local LM Studio or OpenAI-compatible server.'
                  : isLmStudioReachable
                    ? 'LM Studio is reachable, but no models were reported by its model endpoint.'
                    : 'Use the model ID exposed by your local LM Studio server.'}
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

          {/* Relevance Filter */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-white">
                Relevance Filter
              </label>
              <span className="text-sm font-mono text-[#0A84FF]">{Math.round(settings.relevanceThreshold ?? 0)}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              value={settings.relevanceThreshold ?? 0}
              onChange={(e) => {
                const newThreshold = Number(e.target.value);
                console.log('🎚️ Relevance threshold changed to:', newThreshold);
                updateSettings({ ...settings, relevanceThreshold: newThreshold });
              }}
              className="w-full h-2 bg-[#2C2C2E] rounded-lg appearance-none cursor-pointer slider"
              style={{
                background: `linear-gradient(to right, #0A84FF 0%, #0A84FF ${(settings.relevanceThreshold ?? 0)}%, #2C2C2E ${(settings.relevanceThreshold ?? 0)}%, #2C2C2E 100%)`
              }}
            />
            <div className="flex justify-between text-xs text-white/40 mt-1">
              <span>0% (Show All)</span>
              <span>100% (Perfect Only)</span>
            </div>
            <p className="text-xs text-white/40 mt-1">Filter results by relevance percentage</p>
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

          {/* Web Search Toggle */}
          <div className={`flex items-center justify-between p-3 bg-[#2C2C2E] rounded-lg border border-[#3C3C3E] ${enhancedDisabled ? 'opacity-60' : ''}`}>
            <div>
              <div className="text-sm font-medium text-white">Web Search</div>
              <div className="text-xs text-white/40 mt-1">
                {enhancedDisabled ? 'Disabled while Deep Thinking is enabled' : 'Add a clearly separated web findings section'}
              </div>
            </div>
            <button
              onClick={() => handleToggle('enhancedSearch')}
              disabled={enhancedDisabled}
              className={`relative w-12 h-6 rounded-full transition-colors ${settings.enhancedSearch ? 'bg-[#0A84FF]' : 'bg-[#3C3C3E]'
                }`}
            >
              <div
                className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${settings.enhancedSearch ? 'translate-x-6' : 'translate-x-0'
                  }`}
              />
            </button>
          </div>

          <div className="flex items-center justify-between p-3 bg-[#2C2C2E] rounded-lg border border-[#3C3C3E]">
            <div>
              <div className="text-sm font-medium text-white">Brief Concept Index</div>
              <div className="text-xs text-white/40 mt-1">
                {settings.briefConceptIndex ? 'Prefer terse concept-index answers' : 'Prefer fuller grounded answers'}
              </div>
            </div>
            <button
              onClick={() => handleToggle('briefConceptIndex')}
              className={`relative w-12 h-6 rounded-full transition-colors ${settings.briefConceptIndex ? 'bg-[#0A84FF]' : 'bg-[#3C3C3E]'
                }`}
            >
              <div
                className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${settings.briefConceptIndex ? 'translate-x-6' : 'translate-x-0'
                  }`}
              />
            </button>
          </div>

          <div className="p-3 bg-[#2C2C2E] rounded-lg border border-[#3C3C3E] space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-medium text-white">PDF Tree Retrieval</div>
                <div className="text-xs text-white/40 mt-1">
                  Page-aware PDF retrieval provider for the planned tree index.
                </div>
              </div>
              <button
                onClick={() => updatePdfTreeSettings({ enabled: !settings.pdfTree.enabled })}
                className={`relative w-12 h-6 rounded-full transition-colors ${settings.pdfTree.enabled ? 'bg-[#0A84FF]' : 'bg-[#3C3C3E]'}`}
              >
                <div
                  className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${settings.pdfTree.enabled ? 'translate-x-6' : 'translate-x-0'}`}
                />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2">
              {(['ollama', 'lmstudio', 'openrouter', 'openai_compatible'] as PdfTreeProvider[]).map((provider) => (
                <button
                  key={provider}
                  onClick={() => updatePdfTreeSettings({ provider })}
                  className={`py-2 px-2 rounded-lg text-xs font-medium transition-all ${
                    settings.pdfTree.provider === provider
                      ? 'bg-[#0A84FF] text-white'
                      : 'bg-[#1C1C1E] text-white/55 hover:text-white/80'
                  }`}
                >
                  {provider === 'openai_compatible' ? 'OpenAI-Compatible' : provider === 'lmstudio' ? 'LM Studio' : provider === 'openrouter' ? 'OpenRouter' : 'Ollama'}
                </button>
              ))}
            </div>

            {pdfTreeModelOptions.length > 0 && ['ollama', 'lmstudio'].includes(settings.pdfTree.provider) ? (
              <select
                value={settings.pdfTree.model}
                onChange={(e) => updatePdfTreeSettings({ model: e.target.value })}
                disabled={isLoadingModels}
                className="w-full bg-[#1C1C1E] text-white border border-[#3C3C3E] rounded-lg px-3 py-2 focus:outline-none focus:border-[#0A84FF] disabled:opacity-50 appearance-none cursor-pointer"
              >
                {pdfTreeModelOptions.map((model) => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            ) : (
              <input
                value={settings.pdfTree.model}
                onChange={(e) => updatePdfTreeSettings({ model: e.target.value })}
                placeholder={settings.pdfTree.provider === 'openrouter' ? 'openrouter/auto' : 'local-model'}
                className="w-full bg-[#1C1C1E] text-white border border-[#3C3C3E] rounded-lg px-3 py-2 focus:outline-none focus:border-[#0A84FF]"
              />
            )}

            <div className="text-xs text-white/40">
              {pdfTreeStatus
                ? `${pdfTreeStatus.reachable ? 'Reachable' : 'Not reachable'} · ${pdfTreeStatus.provider} · ${pdfTreeStatus.model || settings.pdfTree.model}`
                : 'Provider status not loaded'}
              {pdfTreeStatus?.error ? ` · ${pdfTreeStatus.error}` : ''}
            </div>
          </div>

        </div>

        {/* Indexing Section */}
        <div className="mt-6 pt-4 border-t border-[#2C2C2E]">
          <button
            onClick={() => setIndexExpanded(v => !v)}
            className="w-full flex items-center justify-between text-left group mb-3"
          >
            <div className="flex items-center gap-2">
              <span className="text-base">🗂️</span>
              <span className="text-sm font-semibold text-white">Indexing</span>
            </div>
            <svg
              className={`w-4 h-4 text-white/40 transition-transform ${indexExpanded ? 'rotate-180' : ''}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {indexExpanded && (
            <div className="space-y-4">
              {/* Database selection */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-medium text-white/60 uppercase tracking-wider">
                    Databases
                  </label>
                  <button
                    onClick={() => setIndexDatabases(
                      indexDatabases.size === 5
                        ? new Set()
                        : new Set(['vector', 'graph', 'lightrag', 'pdf-tree', 'mempalace'] as DbKey[])
                    )}
                    disabled={indexRunning}
                    className="text-[10px] text-[#0A84FF] hover:text-[#0A84FF]/80 disabled:opacity-50"
                  >
                    {indexDatabases.size === 5 ? 'deselect all' : 'select all'}
                  </button>
                </div>
                <div className="space-y-1.5">
                  {(Object.entries(DB_META) as [DbKey, { label: string; desc: string }][]).map(([key, meta]) => (
                    <label
                      key={key}
                      className={`flex items-center gap-3 p-2.5 rounded-lg border cursor-pointer transition-colors ${
                        indexDatabases.has(key)
                          ? 'border-[#0A84FF]/40 bg-[#0A84FF]/10'
                          : 'border-[#3C3C3E] bg-[#2C2C2E] hover:border-[#4C4C4E]'
                      } ${indexRunning ? 'opacity-50 pointer-events-none' : ''}`}
                    >
                      <input
                        type="checkbox"
                        checked={indexDatabases.has(key)}
                        onChange={() => {
                          const next = new Set(indexDatabases);
                          next.has(key) ? next.delete(key) : next.add(key);
                          setIndexDatabases(next);
                        }}
                        className="w-3.5 h-3.5 rounded accent-[#0A84FF]"
                      />
                      <div className="min-w-0">
                        <div className="text-xs font-medium text-white">{meta.label}</div>
                        <div className="text-[10px] text-white/40">
                          {key === 'lightrag'
                            ? `${meta.desc} — Markdown notes only`
                            : meta.desc}
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Mode selection */}
              <div>
                <label className="block text-xs font-medium text-white/60 mb-2 uppercase tracking-wider">
                  Mode
                </label>
                <div className="bg-[#2C2C2E] p-1 rounded-xl flex border border-[#3C3C3E]">
                  {(['partial', 'full'] as const).map((m) => (
                    <button
                      key={m}
                      onClick={() => setIndexMode(m)}
                      disabled={indexRunning}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-all capitalize disabled:opacity-50 ${
                        indexMode === m
                          ? 'bg-[#0A84FF] text-white shadow-lg'
                          : 'text-white/40 hover:text-white/60 hover:bg-white/5'
                      }`}
                    >
                      {m}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-white/30 mt-1">
                  {indexMode === 'partial' ? 'Only index new or changed files' : 'Re-index all files from scratch'}
                </p>
              </div>

              {/* Start / Reset buttons */}
              <div className="flex gap-2">
              {indexRunning && (
                <button
                  onClick={resetIndexJob}
                  className="px-3 py-2.5 rounded-lg border border-red-500/40 bg-red-900/20 hover:bg-red-900/40 text-red-400 text-xs font-medium transition-colors"
                  title="Cancel and reset job state"
                >
                  Cancel
                </button>
              )}
              <button
                onClick={handleStartIndexing}
                disabled={indexRunning || indexDatabases.size === 0}
                className="w-full flex items-center justify-center gap-2 bg-[#1C3A5E] hover:bg-[#1C4A7E] disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium py-2.5 px-4 rounded-lg border border-[#0A84FF]/40 transition-colors"
              >
                {indexRunning ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                    Indexing {indexDatabases.size} database{indexDatabases.size !== 1 ? 's' : ''}…
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    {indexDatabases.size === 0
                      ? 'Select a database'
                      : `${indexMode === 'full' ? 'Full' : 'Partial'} Index — ${indexDatabases.size} DB${indexDatabases.size !== 1 ? 's' : ''}`}
                  </>
                )}
              </button>
              </div>

              {/* Output log */}
              {(indexOutput.length > 0 || indexError || indexExitCode !== null) && (
                <div className="rounded-lg border border-[#3C3C3E] overflow-hidden">
                  <div className="flex items-center justify-between px-3 py-1.5 bg-[#2C2C2E] border-b border-[#3C3C3E]">
                    <span className="text-xs text-white/40">Output</span>
                    {indexExitCode !== null && (
                      <span className={`text-xs font-mono ${indexExitCode === 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {indexExitCode === 0 ? '✓ done' : `✗ exit ${indexExitCode}`}
                      </span>
                    )}
                    {indexRunning && (
                      <span className="text-xs text-[#0A84FF] animate-pulse">running…</span>
                    )}
                  </div>
                  <div
                    ref={outputRef}
                    className="h-32 overflow-y-auto bg-[#111] px-3 py-2 font-mono text-[10px] text-white/60 space-y-0.5"
                  >
                    {indexOutput.map((line, i) => (
                      <div key={i} className="leading-relaxed whitespace-pre-wrap break-all">{line}</div>
                    ))}
                    {indexError && (
                      <div className="text-red-400">{indexError}</div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
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
