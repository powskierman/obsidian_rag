import { SearchMode } from '../../lib/types';

interface SearchModePanelProps {
  currentMode: SearchMode;
  onSelect: (mode: SearchMode) => void;
  onClose: () => void;
}

const searchModeGroups = [
  {
    title: 'Available Modes',
    modes: [
      { id: 'vector' as SearchMode, label: 'Vector', description: 'ChromaDB semantic search', icon: '🔍' },
      { id: 'cascading' as SearchMode, label: 'Cascading', description: 'Waterfall retrieval', icon: '🌊' },
      { id: 'deep-thinking' as SearchMode, label: 'Deep Thinking', description: 'Agentic reasoning', icon: '🧠' }
    ]
  }
];

export default function SearchModePanel({ currentMode, onSelect, onClose }: SearchModePanelProps) {
  const handleSelect = (mode: SearchMode) => {
    onSelect(mode);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-[#1C1C1E] rounded-2xl border border-[#2C2C2E] p-6 w-[400px] max-w-[90vw]" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🔍</span>
            <h2 className="text-xl font-bold text-white">Search Mode</h2>
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

        <p className="text-sm text-white/60 mb-4">Choose your search method:</p>

        <div className="space-y-4">
          {searchModeGroups.map((group) => (
            <div key={group.title} className="space-y-2">
              <div className="text-xs font-semibold text-white/40 uppercase tracking-wider px-1">
                {group.title}
              </div>
              {group.modes.map((mode) => (
                <label
                  key={mode.id}
                  className={`flex items-center gap-3 p-4 rounded-xl border cursor-pointer transition-all ${currentMode === mode.id
                      ? 'bg-[#0A84FF]/10 border-[#0A84FF]'
                      : 'bg-[#1C1C1E] border-[#2C2C2E] hover:border-white/20'
                    }`}
                >
                  <input
                    type="radio"
                    name="searchMode"
                    value={mode.id}
                    checked={currentMode === mode.id}
                    onChange={() => handleSelect(mode.id)}
                    className="w-5 h-5 text-[#0A84FF] bg-transparent border-2 border-white/20 focus:ring-2 focus:ring-[#0A84FF] cursor-pointer"
                  />
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
          ))}
        </div>
      </div>
    </div>
  );
}
