import { useApp } from '../../context/AppContext';

export default function EnhancedSearchToggle() {
  const { settings, updateSettings } = useApp();

  const handleToggle = () => {
    updateSettings({ enhancedSearch: !settings.enhancedSearch });
  };

  return (
    <button
      onClick={handleToggle}
      className="w-full flex items-center justify-between p-3 rounded-lg bg-[#1C1C1E] border border-[#2C2C2E] hover:border-[#0A84FF]/50 transition-all group"
    >
      <div className="flex items-center gap-3">
        <span className="text-xl">🌐</span>
        <div className="text-left">
          <div className="text-[10px] text-white/40 uppercase tracking-wider font-semibold">
            Enhanced Search
          </div>
          <div className="text-sm text-white font-medium">
            {settings.enhancedSearch ? 'Enabled' : 'Disabled'}
          </div>
        </div>
      </div>
      <div
        className={`relative w-12 h-6 rounded-full transition-colors ${
          settings.enhancedSearch ? 'bg-[#0A84FF]' : 'bg-[#3C3C3E]'
        }`}
      >
        <div
          className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
            settings.enhancedSearch ? 'translate-x-6' : 'translate-x-0'
          }`}
        />
      </div>
    </button>
  );
}
