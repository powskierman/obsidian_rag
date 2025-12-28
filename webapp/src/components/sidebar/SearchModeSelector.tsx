import React from 'react';
import { useApp } from '../../context/AppContext';
import { SearchMode } from '../../lib/types';

const searchModes = [
  {
    id: 'vector' as SearchMode,
    label: 'Vector',
    description: 'Fast semantic search',
    icon: '🔍'
  },
  {
    id: 'knowledge-graph' as SearchMode,
    label: 'Knowledge-Graph',
    description: 'Deep reasoning & connections',
    icon: '🧠'
  },
  {
    id: 'hybrid' as SearchMode,
    label: 'Hybrid',
    description: 'Best of both worlds',
    icon: '🔗'
  }
];

export default function SearchModeSelector() {
  const { searchMode, setSearchMode } = useApp();

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <span className="text-lg">🔍</span>
          <label className="text-xs font-semibold text-white/40 uppercase tracking-wider">
            Search Mode
          </label>
        </div>
        <p className="text-xs text-white/50 pl-7">Choose search method:</p>
      </div>

      <div className="space-y-2">
        {searchModes.map((mode) => (
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
                <span className="text-sm font-medium text-white">{mode.label}</span>
              </div>
              <div className="text-xs text-white/50 mt-0.5">{mode.description}</div>
            </div>
            <div
              className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                searchMode === mode.id ? 'border-[#0A84FF]' : 'border-white/20'
              }`}
            >
              {searchMode === mode.id && (
                <div className="w-2 h-2 rounded-full bg-[#0A84FF]" />
              )}
            </div>
          </label>
        ))}
      </div>
    </div>
  );
}
