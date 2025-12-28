import React, { useState, useEffect } from 'react';
import { useApp } from '../../context/AppContext';
import { api } from '../../lib/api';

export default function ServicesStatus() {
  const { services, updateServices } = useApp();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const checkServices = async () => {
    setIsRefreshing(true);
    try {
      // Get vector DB stats
      const stats = await api.getStats();

      // Get Ollama models
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
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg">📊</span>
          <label className="text-xs font-semibold text-white/40 uppercase tracking-wider">
            Services
          </label>
        </div>
        <button
          onClick={checkServices}
          disabled={isRefreshing}
          className="text-[10px] text-[#0A84FF] hover:underline disabled:opacity-50"
        >
          {isRefreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      <div className="bg-black/20 rounded-xl p-4 space-y-3 border border-[#2C2C2E]">
        {/* Vector DB */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-white/60 flex items-center gap-2">
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                services.vectorDB.available ? 'bg-green-500' : 'bg-red-500'
              }`}
            ></div>
            Vector DB
          </span>
          <span className="text-white font-mono font-medium">
            {services.vectorDB.chunks.toLocaleString()} chunks
          </span>
        </div>

        {/* Knowledge Graph */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-white/60 flex items-center gap-2">
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                services.knowledgeGraph.available ? 'bg-green-500' : 'bg-red-500'
              }`}
            ></div>
            Graph Service
          </span>
          <span className="text-white font-mono font-medium">
            {services.knowledgeGraph.available ? 'Online' : 'Offline'}
          </span>
        </div>

        {/* Ollama Models */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-white/60 flex items-center gap-2">
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                services.ollama.available ? 'bg-green-500' : 'bg-red-500'
              }`}
            ></div>
            Ollama Models
          </span>
          <span className="text-white font-mono font-medium">
            {services.ollama.models.length} available
          </span>
        </div>
      </div>
    </div>
  );
}
