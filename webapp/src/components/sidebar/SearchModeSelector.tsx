import React, { useState, useRef, useEffect } from 'react';
import { useApp } from '../../context/AppContext';
import { SearchMode } from '../../lib/types';
import { ChevronDown } from 'lucide-react';

const searchModes = [
  {
    id: 'vector' as SearchMode,
    label: 'Vector',
    description: 'Fast semantic search',
    icon: '🔮'
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
  },
  {
    id: 'cascading' as SearchMode,
    label: 'Cascading',
    description: 'Multi-hop Waterfall',
    icon: '🌊'
  }
];

export default function SearchModeSelector() {
  const { searchMode, setSearchMode } = useApp();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentMode = searchModes.find(m => m.id === searchMode) || searchModes[2];

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="space-y-1 relative" ref={dropdownRef}>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-lg">🔍</span>
        <label className="text-xs font-semibold text-white/40 uppercase tracking-wider">
          Search Mode
        </label>
      </div>

      {/* Trigger Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-2.5 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition-all text-left group"
      >
        <div className="flex items-center gap-2.5">
          <span className="text-lg">{currentMode.icon}</span>
          <div>
            <div className="text-sm font-medium text-white group-hover:text-[#fbbf24] transition-colors">
              {currentMode.label}
            </div>
          </div>
        </div>
        <ChevronDown size={14} className={`text-white/40 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown Popup */}
      {isOpen && (
        <div className="absolute top-full left-0 w-full mt-2 bg-[#1C1C1E] border border-white/10 rounded-xl shadow-xl z-50 overflow-hidden backdrop-blur-xl">
          <div className="p-1 space-y-0.5">
            {searchModes.map((mode) => (
              <button
                key={mode.id}
                onClick={() => {
                  setSearchMode(mode.id);
                  setIsOpen(false);
                }}
                className={`w-full flex items-center gap-3 p-2.5 rounded-lg transition-all text-left ${searchMode === mode.id
                    ? 'bg-[#fbbf24]/10 text-[#fbbf24]'
                    : 'hover:bg-white/5 text-gray-300 hover:text-white'
                  }`}
              >
                <span className="text-lg">{mode.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{mode.label}</div>
                  <div className="text-[10px] opacity-60 truncate">{mode.description}</div>
                </div>
                {searchMode === mode.id && (
                  <div className="w-1.5 h-1.5 rounded-full bg-[#fbbf24]" />
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
