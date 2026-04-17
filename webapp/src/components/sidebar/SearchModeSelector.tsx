import React from 'react';
import { useApp } from '../../context/AppContext';
import { SearchMode, ResearchDepth, DataSource } from '../../lib/types';

const MODES: { id: SearchMode; label: string; description: string; icon: string }[] = [
  { id: 'ask',        label: 'Ask',        description: 'Fast single-pass answer from your notes', icon: '💬' },
  { id: 'research',   label: 'Research',   description: 'Staged retrieval — staged, deep, or auto-depth', icon: '🔎' },
  { id: 'investigate',label: 'Investigate',description: 'Agentic: plans, searches, reflects — streaming', icon: '🧠' },
];

const DEPTHS: { id: ResearchDepth; label: string; hint: string }[] = [
  { id: 'auto',    label: 'Auto',     hint: 'Classifier picks depth' },
  { id: 'shallow', label: 'Quick',    hint: 'Single-pass vector' },
  { id: 'staged',  label: 'Thorough', hint: 'Graph → LightRAG → vector' },
  { id: 'full',    label: 'Full',     hint: '+ full-note MCP reads' },
];

const SOURCE_OPTIONS: { id: DataSource; label: string; icon: string }[] = [
  { id: 'vault',     label: 'Vault',          icon: '📂' },
  { id: 'mempalace', label: 'Memory Palace',  icon: '🏛️' },
  { id: 'web',       label: 'Web',            icon: '🌐' },
];

export default function SearchModeSelector() {
  const { searchMode, setSearchMode, settings, setResearchDepth, setDataSources } = useApp();
  const depth = settings.researchDepth ?? 'auto';
  const dataSources = settings.dataSources ?? ['vault'];

  const toggleSource = (src: DataSource) => {
    const next = dataSources.includes(src)
      ? dataSources.filter(s => s !== src)
      : [...dataSources, src];
    // Always keep at least vault.
    setDataSources(next.length ? next : ['vault']);
  };

  return (
    <div className="space-y-4">
      {/* Mode radios */}
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <span className="text-lg">🔍</span>
          <label className="text-xs font-semibold text-white/40 uppercase tracking-wider">
            Search Mode
          </label>
        </div>
        <div className="space-y-2 mt-1">
          {MODES.map((mode) => (
            <label
              key={mode.id}
              className={`flex items-center justify-between p-3 rounded-xl border cursor-pointer transition-all ${
                searchMode === mode.id
                  ? 'bg-[#0A84FF]/10 border-[#0A84FF]'
                  : 'bg-[#1C1C1E] border-[#2C2C2E] hover:border-white/20'
              }`}
            >
              <input
                type="radio"
                name="searchMode"
                checked={searchMode === mode.id}
                onChange={() => setSearchMode(mode.id)}
                className="hidden"
              />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm">{mode.icon}</span>
                  <span className="text-sm font-medium text-white">{mode.label}</span>
                </div>
                <div className="text-xs text-white/50 mt-0.5 pl-5">{mode.description}</div>
              </div>
              <div className={`w-4 h-4 rounded-full border flex items-center justify-center flex-shrink-0 ${
                searchMode === mode.id ? 'border-[#0A84FF]' : 'border-white/20'
              }`}>
                {searchMode === mode.id && <div className="w-2 h-2 rounded-full bg-[#0A84FF]" />}
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Research depth — only shown when mode is research */}
      {searchMode === 'research' && (
        <div className="space-y-1">
          <label className="text-xs font-semibold text-white/40 uppercase tracking-wider pl-1">
            Depth
          </label>
          <div className="grid grid-cols-2 gap-1 mt-1">
            {DEPTHS.map((d) => (
              <button
                key={d.id}
                onClick={() => setResearchDepth(d.id)}
                title={d.hint}
                className={`px-2 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  depth === d.id
                    ? 'bg-[#0A84FF] text-white'
                    : 'bg-[#1C1C1E] border border-[#2C2C2E] text-white/60 hover:border-white/20'
                }`}
              >
                {d.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Sources — vault always on; mempalace/web are additive */}
      <div className="space-y-1">
        <label className="text-xs font-semibold text-white/40 uppercase tracking-wider pl-1">
          Sources
        </label>
        <div className="flex flex-col gap-1 mt-1">
          {SOURCE_OPTIONS.map((src) => {
            const checked = dataSources.includes(src.id);
            const locked = src.id === 'vault'; // vault always required
            return (
              <label
                key={src.id}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-all ${
                  checked
                    ? 'bg-[#0A84FF]/10 border-[#0A84FF]/50 text-white'
                    : 'bg-[#1C1C1E] border-[#2C2C2E] text-white/50 hover:border-white/20'
                } ${locked ? 'opacity-70 cursor-default' : ''}`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={locked}
                  onChange={() => !locked && toggleSource(src.id)}
                  className="hidden"
                />
                <span className="text-sm">{src.icon}</span>
                <span className="text-xs font-medium">{src.label}</span>
                {locked && <span className="ml-auto text-[10px] text-white/30">always on</span>}
              </label>
            );
          })}
        </div>
      </div>
    </div>
  );
}
