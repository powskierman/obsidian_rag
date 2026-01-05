import React from 'react';
import { useApp } from '../../context/AppContext';

export default function SettingsPanel() {
  const { settings, updateSettings, services } = useApp();

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-lg">⚙️</span>
        <label className="text-xs font-semibold text-white/40 uppercase tracking-wider">
          Settings
        </label>
      </div>

      {/* Model Selector */}
      <div className="space-y-2">
        <label className="text-xs text-white/60">Model</label>
        <select
          value={settings.model}
          onChange={(e) => updateSettings({ model: e.target.value })}
          className="w-full bg-[#000000]/50 border border-[#2C2C2E] rounded-xl p-2.5 text-sm text-white focus:outline-none focus:border-[#0A84FF] focus:ring-1 focus:ring-[#0A84FF]"
        >
          {services.ollama.models.length > 0 ? (
            services.ollama.models.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))
          ) : (
            <option value="llama3.2:latest">llama3.2:latest</option>
          )}
        </select>
      </div>

      {/* Sources Slider */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs text-white/60">Sources</label>
          <span className="text-xs text-white/80 font-mono">{settings.sources}</span>
        </div>
        <input
          type="range"
          min="1"
          max="50"
          value={settings.sources}
          onChange={(e) => updateSettings({ sources: parseInt(e.target.value) })}
          className="w-full h-1 bg-[#2C2C2E] rounded-lg appearance-none cursor-pointer accent-[#0A84FF]"
        />
        <div className="flex justify-between text-[10px] text-white/30">
          <span>1</span>
          <span>50</span>
        </div>
      </div>

      {/* Temperature Slider */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs text-white/60">Temperature</label>
          <span className="text-xs text-white/80 font-mono">
            {settings.temperature.toFixed(2)}
          </span>
        </div>
        <input
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={settings.temperature}
          onChange={(e) => updateSettings({ temperature: parseFloat(e.target.value) })}
          className="w-full h-1 bg-[#2C2C2E] rounded-lg appearance-none cursor-pointer accent-[#0A84FF]"
        />
        <div className="flex justify-between text-[10px] text-white/30">
          <span>0.0</span>
          <span>1.0</span>
        </div>
      </div>

      {/* Distance Threshold Slider */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs text-white/60">Filter Threshold</label>
          <span className="text-xs text-white/80 font-mono">
            {settings.distanceThreshold.toFixed(1)}
          </span>
        </div>
        <input
          type="range"
          min="0"
          max="15"
          step="0.5"
          value={settings.distanceThreshold}
          onChange={(e) => updateSettings({ distanceThreshold: parseFloat(e.target.value) })}
          className="w-full h-1 bg-[#2C2C2E] rounded-lg appearance-none cursor-pointer accent-[#0A84FF]"
        />
        <div className="flex justify-between text-[10px] text-white/30">
          <span>0.0 (strict)</span>
          <span>15.0 (loose)</span>
        </div>
      </div>

      {/* Checkboxes */}
      <div className="space-y-2">
        <label className="flex items-center gap-2 cursor-pointer group">
          <input
            type="checkbox"
            checked={settings.showSources}
            onChange={(e) => updateSettings({ showSources: e.target.checked })}
            className="w-4 h-4 rounded border-[#2C2C2E] bg-[#1C1C1E] text-[#0A84FF] focus:ring-[#0A84FF] focus:ring-offset-0"
          />
          <span className="text-sm text-white/80 group-hover:text-white transition-colors">
            Show Sources
          </span>
        </label>

        <label className="flex items-center gap-2 cursor-pointer group">
          <input
            type="checkbox"
            checked={settings.enhancedSearch}
            onChange={(e) => updateSettings({ enhancedSearch: e.target.checked })}
            className="w-4 h-4 rounded border-[#2C2C2E] bg-[#1C1C1E] text-[#0A84FF] focus:ring-[#0A84FF] focus:ring-offset-0"
          />
          <span className="text-sm text-white/80 group-hover:text-white transition-colors">
            Enhanced Search
          </span>
        </label>
      </div>
    </div>
  );
}
