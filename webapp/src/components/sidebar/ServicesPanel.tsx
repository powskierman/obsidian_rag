import { useState, useEffect } from 'react';
import { useApp } from '../../context/AppContext';
import { api } from '../../lib/api';

interface ServicesPanelProps {
  onClose: () => void;
}

export default function ServicesPanel({ onClose }: ServicesPanelProps) {
  const { services, updateServices } = useApp();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const checkServices = async () => {
    setIsRefreshing(true);
    try {
      const stats = await api.getStats();
      const ollamaModels = await api.getOllamaModels();

      updateServices({
        vectorDB: {
          available: stats.documents > 0,
          chunks: stats.documents,
        },
        knowledgeGraph: {
          available: stats.graph !== null && stats.graph.graph_loaded === true,
          entities: stats.graph?.nodes || 0,
          relationships: stats.graph?.edges || 0,
        },
        ollama: {
          available: ollamaModels.length > 0,
          models: ollamaModels,
        },
      });
    } catch (error) {
      console.error('Failed to check services:', error);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    checkServices();
  }, []);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-[#1C1C1E] rounded-2xl border border-[#2C2C2E] p-6 w-[450px] max-w-[90vw]" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <span className="text-2xl">📊</span>
            <h2 className="text-xl font-bold text-white">Services Status</h2>
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

        <div className="flex items-center justify-between mb-4">
          <p className="text-sm text-white/60">Backend services monitoring</p>
          <button
            onClick={checkServices}
            disabled={isRefreshing}
            className="text-xs text-[#0A84FF] hover:underline disabled:opacity-50"
          >
            {isRefreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>

        <div className="space-y-3">
          {/* Vector DB */}
          <div className="bg-black/20 rounded-xl p-4 border border-[#2C2C2E]">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${services.vectorDB.available ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-white font-medium">Vector DB</span>
              </div>
              <span className={`text-xs px-2 py-1 rounded ${services.vectorDB.available ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'}`}>
                {services.vectorDB.available ? 'Online' : 'Offline'}
              </span>
            </div>
            <div className="text-2xl font-bold text-white font-mono">
              {services.vectorDB.chunks.toLocaleString()}
              <span className="text-sm text-white/40 ml-2">chunks</span>
            </div>
            <div className="text-xs text-white/40 mt-1">Port 8000 • ChromaDB</div>
          </div>

          {/* Knowledge Graph */}
          <div className="bg-black/20 rounded-xl p-4 border border-[#2C2C2E]">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${services.knowledgeGraph.available ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-white font-medium">Knowledge Graph</span>
              </div>
              <span className={`text-xs px-2 py-1 rounded ${services.knowledgeGraph.available ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'}`}>
                {services.knowledgeGraph.available ? 'Online' : 'Offline'}
              </span>
            </div>
            {services.knowledgeGraph.available ? (
              <div className="grid grid-cols-2 gap-3 mt-2">
                <div>
                  <div className="text-xl font-bold text-white font-mono">
                    {services.knowledgeGraph.entities.toLocaleString()}
                  </div>
                  <div className="text-xs text-white/40">entities</div>
                </div>
                <div>
                  <div className="text-xl font-bold text-white font-mono">
                    {services.knowledgeGraph.relationships.toLocaleString()}
                  </div>
                  <div className="text-xs text-white/40">relationships</div>
                </div>
              </div>
            ) : (
              <div className="text-sm text-white/40 mt-2">Service not available</div>
            )}
            <div className="text-xs text-white/40 mt-2">Port 8002 • NetworkX</div>
          </div>

          {/* Ollama */}
          <div className="bg-black/20 rounded-xl p-4 border border-[#2C2C2E]">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${services.ollama.available ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-white font-medium">Ollama</span>
              </div>
              <span className={`text-xs px-2 py-1 rounded ${services.ollama.available ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'}`}>
                {services.ollama.available ? 'Online' : 'Offline'}
              </span>
            </div>
            {services.ollama.available ? (
              <>
                <div className="text-2xl font-bold text-white font-mono">
                  {services.ollama.models.length}
                  <span className="text-sm text-white/40 ml-2">models</span>
                </div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {services.ollama.models.map((model) => (
                    <span key={model} className="text-xs bg-white/5 text-white/60 px-2 py-1 rounded">
                      {model}
                    </span>
                  ))}
                </div>
              </>
            ) : (
              <div className="text-sm text-white/40 mt-2">Service not available</div>
            )}
            <div className="text-xs text-white/40 mt-2">Port 11434 • Local LLMs</div>
          </div>
        </div>
      </div>
    </div>
  );
}
