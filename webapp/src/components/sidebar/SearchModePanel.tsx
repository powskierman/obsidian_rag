import React from 'react';
import { SearchMode, ResearchDepth, DataSource } from '../../lib/types';

interface SearchModePanelProps {
  currentMode: SearchMode;
  currentDepth: ResearchDepth;
  currentSources: DataSource[];
  onSelectMode: (mode: SearchMode) => void;
  onSelectDepth: (depth: ResearchDepth) => void;
  onToggleSource: (source: DataSource) => void;
  onClose: () => void;
}

const MODES = [
  { id: 'ask'        as SearchMode, label: 'Ask',         description: 'Fast single-pass answer', icon: '💬' },
  { id: 'research'   as SearchMode, label: 'Research',    description: 'Staged retrieval — staged, deep, or auto-depth', icon: '🔎' },
  { id: 'investigate'as SearchMode, label: 'Investigate', description: 'Agentic: plan · search · reflect (streaming)', icon: '🧠' },
];

const DEPTHS: { id: ResearchDepth; label: string; hint: string }[] = [
  { id: 'auto',    label: 'Auto',     hint: 'Classifier picks depth' },
  { id: 'shallow', label: 'Quick',    hint: 'Single-pass vector search' },
  { id: 'staged',  label: 'Thorough', hint: 'Graph → LightRAG → vector' },
  { id: 'full',    label: 'Full',     hint: '+ full-note MCP reads' },
];

const SOURCES: { id: DataSource; label: string; icon: string; locked?: boolean }[] = [
  { id: 'vault',     label: 'Vault',         icon: '📂', locked: true },
  { id: 'mempalace', label: 'Memory Palace', icon: '🏛️' },
  { id: 'web',       label: 'Web',           icon: '🌐' },
];

export default function SearchModePanel({
  currentMode, currentDepth, currentSources,
  onSelectMode, onSelectDepth, onToggleSource, onClose,
}: SearchModePanelProps) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-[#1C1C1E] rounded-2xl border border-[#2C2C2E] p-6 w-[420px] max-w-[90vw] max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🔍</span>
            <h2 className="text-xl font-bold text-white">Search Mode</h2>
          </div>
          <button onClick={onClose} className="text-white/40 hover:text-white transition-colors">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Mode */}
        <p className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Mode</p>
        <div className="space-y-2 mb-5">
          {MODES.map((mode) => (
            <label key={mode.id} className={`flex items-center gap-3 p-4 rounded-xl border cursor-pointer transition-all ${
              currentMode === mode.id ? 'bg-[#0A84FF]/10 border-[#0A84FF]' : 'bg-[#1C1C1E] border-[#2C2C2E] hover:border-white/20'
            }`}>
              <input type="radio" name="searchMode" value={mode.id} checked={currentMode === mode.id}
                onChange={() => { onSelectMode(mode.id); onClose(); }} className="w-5 h-5 text-[#0A84FF] bg-transparent border-2 border-white/20 cursor-pointer" />
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-lg">{mode.icon}</span>
                  <span className="text-white font-medium">{mode.label}</span>
                </div>
                <p className="text-sm text-white/60">{mode.description}</p>
              </div>
            </label>
          ))}
        </div>

        {/* Research depth */}
        {currentMode === 'research' && (
          <>
            <p className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Research Depth</p>
            <div className="grid grid-cols-2 gap-2 mb-5">
              {DEPTHS.map((d) => (
                <button key={d.id} onClick={() => onSelectDepth(d.id)} title={d.hint}
                  className={`px-3 py-2 rounded-xl border text-sm font-medium transition-all ${
                    currentDepth === d.id ? 'bg-[#0A84FF] border-[#0A84FF] text-white' : 'bg-[#1C1C1E] border-[#2C2C2E] text-white/60 hover:border-white/20'
                  }`}>
                  {d.label}
                  <div className="text-[10px] text-inherit opacity-60 mt-0.5">{d.hint}</div>
                </button>
              ))}
            </div>
          </>
        )}

        {/* Sources */}
        <p className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Sources</p>
        <div className="space-y-2">
          {SOURCES.map((src) => {
            const checked = currentSources.includes(src.id);
            return (
              <label key={src.id} className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${
                checked ? 'bg-[#0A84FF]/10 border-[#0A84FF]/50 text-white' : 'bg-[#1C1C1E] border-[#2C2C2E] text-white/60 hover:border-white/20'
              } ${src.locked ? 'cursor-default opacity-70' : ''}`}>
                <input type="checkbox" checked={checked} disabled={src.locked}
                  onChange={() => !src.locked && onToggleSource(src.id)} className="w-4 h-4 cursor-pointer" />
                <span className="text-lg">{src.icon}</span>
                <span className="font-medium">{src.label}</span>
                {src.locked && <span className="ml-auto text-xs text-white/30">always on</span>}
              </label>
            );
          })}
        </div>
      </div>
    </div>
  );
}
