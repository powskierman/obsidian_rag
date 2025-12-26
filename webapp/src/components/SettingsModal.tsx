import React from 'react';
import { api } from '@/lib/api';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  searchMode: string;
  setSearchMode: (mode: string) => void;
  webSearchEnabled: boolean;
  setWebSearchEnabled: (enabled: boolean) => void;
  model: string;
  setModel: (model: string) => void;
  sources: number;
  setSources: (n: number) => void;
  temperature: number;
  setTemperature: (t: number) => void;
  showSources: boolean;
  setShowSources: (show: boolean) => void;
  enhancedSearch: boolean;
  setEnhancedSearch: (enabled: boolean) => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  searchMode,
  setSearchMode,
  webSearchEnabled,
  setWebSearchEnabled,
  model,
  setModel,
  sources,
  setSources,
  temperature,
  setTemperature,
  showSources,
  setShowSources,
  enhancedSearch,
  setEnhancedSearch,
}) => {
  const [stats, setStats] = React.useState({
    vectorChunks: 0,
    graphEntities: 0,
    graphRelationships: 0,
    ollamaModels: 0,
    loading: true
  });

  React.useEffect(() => {
    if (isOpen) {
      const fetchStats = async () => {
        try {
          const [v, g, o] = await Promise.all([
            api.getVectorStats(),
            api.getGraphStats(),
            api.getOllamaModels()
          ]);
          setStats({
            vectorChunks: v.chunks,
            graphEntities: g.nodes || 0,
            graphRelationships: g.edges || 0,
            ollamaModels: o.count,
            loading: false
          });
        } catch (e) {
          console.error("Failed to fetch stats", e);
          setStats(s => ({ ...s, loading: false }));
        }
      };
      fetchStats();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content glass-panel" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Search Settings</h3>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <div className="setting-group">
          <label className="setting-label">Search Mode</label>
          <div className="mode-options">
            <button
              className={`mode-btn ${searchMode === 'vector' ? 'active' : ''}`}
              onClick={() => setSearchMode('vector')}
            >
              <span className="icon">⚡</span>
              <span className="label">Vector</span>
              <span className="desc">Fast, content-focused</span>
            </button>

            <button
              className={`mode-btn ${searchMode === 'graph' ? 'active' : ''}`}
              onClick={() => setSearchMode('graph')}
            >
              <span className="icon">🕸️</span>
              <span className="label">Graph</span>
              <span className="desc">Structure & Relations</span>
            </button>

            <button
              className={`mode-btn ${searchMode === 'hybrid' ? 'active' : ''}`}
              onClick={() => setSearchMode('hybrid')}
            >
              <span className="icon">🧠</span>
              <span className="label">Hybrid</span>
              <span className="desc">Best of both</span>
            </button>
          </div>
        </div>

        <div className="setting-group">
          <label className="setting-label">AI Model</label>
          <div className="mode-options">
            <button
              className={`mode-btn ${model === 'gemini-3-pro-preview' ? 'active' : ''}`}
              onClick={() => setModel('gemini-3-pro-preview')}
            >
              <span className="icon">✨</span>
              <span className="label">Gemini 3 Pro</span>
              <span className="desc">Preview</span>
            </button>

            <button
              className={`mode-btn ${model === 'anthropic/claude-haiku-4.5' ? 'active' : ''}`}
              onClick={() => setModel('anthropic/claude-haiku-4.5')}
            >
              <span className="icon">🚀</span>
              <span className="label">Claude 4.5</span>
              <span className="desc">Haiku Speed</span>
            </button>

            <button
              className={`mode-btn ${model === 'moonshotai/kimi-k2-0905' ? 'active' : ''}`}
              onClick={() => setModel('moonshotai/kimi-k2-0905')}
            >
              <span className="icon">🌙</span>
              <span className="label">Kimi K2</span>
              <span className="desc">Long Context</span>
            </button>
          </div>
        </div>

        <div className="setting-group">
          <label className="setting-label row">
            <span>Enhanced Search (Web)</span>
            <div className={`toggle-switch ${webSearchEnabled ? 'on' : 'off'}`} onClick={() => setWebSearchEnabled(!webSearchEnabled)}>
              <div className="toggle-thumb" />
            </div>
          </label>
          <p className="setting-desc">
            Enables the "Deep Thinking" agent to search the web for external context.
          </p>
        </div>

        <div className="setting-group">
          <label className="setting-label">Sources: {sources}</label>
          <input
            type="range"
            min="1"
            max="50"
            value={sources}
            onChange={(e) => setSources(parseInt(e.target.value))}
            className="slider"
          />
        </div>

        <div className="setting-group">
          <label className="setting-label">Temperature: {temperature}</label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={temperature}
            onChange={(e) => setTemperature(parseFloat(e.target.value))}
            className="slider"
          />
        </div>

        <div className="setting-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={showSources}
              onChange={(e) => setShowSources(e.target.checked)}
            />
            <span>Show Sources</span>
          </label>
        </div>

        <div className="services-status">
          <h4>Services Status</h4>
          <div className="status-item">
            <span className="status-icon">✅</span>
            <span className="status-text">Vector DB: <strong>{stats.vectorChunks.toLocaleString()}</strong> chunks</span>
          </div>
          <div className="status-item">
            <span className="status-icon">✅</span>
            <span className="status-text">Knowledge Graph: <strong>{stats.graphEntities}</strong> entities, <strong>{stats.graphRelationships}</strong> relationships</span>
          </div>
          <div className="status-item">
            <span className="status-icon">✅</span>
            <span className="status-text">Ollama: <strong>{stats.ollamaModels}</strong> models available</span>
          </div>
        </div>
      </div>

      <style jsx>{`
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.7);
          backdrop-filter: blur(5px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }

        .modal-content {
          width: 90%;
          max-width: 600px; /* Increased from 500px */
          max-height: 85vh; /* Prevent it from being taller than screen */
          overflow-y: auto; /* Enable scrolling */
          padding: 2rem;
          background: rgba(10, 15, 30, 0.9);
          border-radius: 20px;
        }
        
        /* Custom Scrollbar for Modal */
        .modal-content::-webkit-scrollbar {
          width: 8px;
        }
        .modal-content::-webkit-scrollbar-track {
          background: rgba(255, 255, 255, 0.05);
          border-radius: 4px;
        }
        .modal-content::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.2);
          border-radius: 4px;
        }
        .modal-content::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 255, 255, 0.3);
        }

        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 2rem;
        }

        .modal-header h3 {
          margin: 0;
          color: var(--neon-blue);
          font-size: 1.5rem;
        }

        .close-btn {
          background: none;
          border: none;
          color: rgba(255,255,255,0.5);
          font-size: 2rem;
          cursor: pointer;
          line-height: 1;
        }
        .close-btn:hover { color: white; }

        .setting-group {
          margin-bottom: 2rem;
        }

        .setting-label {
          display: block;
          color: var(--text-secondary);
          margin-bottom: 1rem;
          font-size: 0.9rem;
          text-transform: uppercase;
          letter-spacing: 1px;
        }
        
        .setting-label.row {
           display: flex;
           justify-content: space-between;
           align-items: center;
           margin-bottom: 0.5rem;
           cursor: pointer;
           color: white;
           text-transform: none;
           font-size: 1.1rem;
        }

        .setting-desc {
            font-size: 0.85rem;
            color: rgba(255,255,255,0.5);
            line-height: 1.4;
            margin-top: 0;
        }

        .mode-options {
          display: grid;
          grid-template-columns: 1fr 1fr 1fr;
          gap: 1rem;
        }

        .mode-btn {
          background: rgba(255,255,255,0.05);
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 12px;
          padding: 1rem 0.5rem;
          color: rgba(255,255,255,0.7);
          cursor: pointer;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.5rem;
          transition: all 0.2s;
        }

        .mode-btn:hover {
          background: rgba(255,255,255,0.1);
        }

        .mode-btn.active {
          background: rgba(0, 210, 255, 0.1);
          border-color: var(--neon-blue);
          color: white;
          box-shadow: 0 0 15px rgba(0, 210, 255, 0.2);
        }

        .mode-btn .icon { font-size: 1.5rem; }
        .mode-btn .label { font-weight: bold; font-size: 0.9rem; }
        .mode-btn .desc { font-size: 0.7rem; opacity: 0.6; text-align: center; }

        /* Toggle Switch */
        .toggle-switch {
            width: 50px;
            height: 28px;
            background: rgba(255,255,255,0.1);
            border-radius: 14px;
            position: relative;
            transition: all 0.3s;
            cursor: pointer;
        }
        
        .toggle-switch.on {
            background: var(--neon-blue);
            box-shadow: 0 0 10px rgba(0, 210, 255, 0.3);
        }
        
        .toggle-thumb {
            width: 22px;
            height: 22px;
            background: white;
            border-radius: 50%;
            position: absolute;
            top: 3px;
            left: 3px;
            transition: all 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
        }
        
        .toggle-switch.on .toggle-thumb {
            transform: translateX(22px);
        }

        .slider {
          -webkit-appearance: none;
          width: 100%;
          height: 6px;
          background: rgba(255,255,255,0.1);
          border-radius: 3px;
          outline: none;
          margin-top: 0.5rem;
        }

        .slider::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          width: 18px;
          height: 18px;
          border-radius: 50%;
          background: var(--neon-blue);
          cursor: pointer;
          transition: transform 0.1s;
        }

        .slider::-webkit-slider-thumb:hover {
          transform: scale(1.1);
        }

        .checkbox-label {
          display: flex;
          align-items: center;
          gap: 0.8rem;
          color: white;
          cursor: pointer;
        }

        .checkbox-label input {
          width: 18px;
          height: 18px;
          accent-color: var(--neon-blue);
        }

        .services-status {
            margin-top: 2rem;
            padding-top: 1.5rem;
            border-top: 1px solid rgba(255,255,255,0.1);
        }
        .services-status h4 {
            color: var(--neon-purple);
            margin-bottom: 1rem;
            font-size: 1.1rem;
        }
        .status-item {
            display: flex;
            align-items: center;
            gap: 0.8rem;
            margin-bottom: 0.8rem;
            font-size: 0.95rem;
            color: rgba(255,255,255,0.9);
        }
        .status-icon { font-size: 1.1rem; }
        .status-item strong { color: var(--neon-blue); font-weight: 600; }
      `}</style>
    </div>
  );
};
