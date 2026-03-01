import React, { useState, useEffect } from 'react';
import { useApp } from '../../context/AppContext';
import { api } from '../../lib/api';
import {
  getKnowledgeGraphServiceState,
  getServiceTone,
  getVectorServiceState,
} from '../../lib/serviceStatus';

export default function ServicesStatus() {
  const { services, updateServices } = useApp();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const checkServices = async () => {
    setIsRefreshing(true);
    try {
      // Get vector DB stats
      const stats = await api.getStats();
      const vectorStatus = getVectorServiceState(stats.documents);
      const knowledgeGraphStatus = getKnowledgeGraphServiceState(stats.graph);

      // Get Ollama models
      const ollamaModels = await api.getOllamaModels();

      updateServices({
        vectorDB: {
          available: vectorStatus === 'online',
          status: vectorStatus,
          chunks: stats.documents,
        },
        knowledgeGraph: {
          available: knowledgeGraphStatus === 'online',
          status: knowledgeGraphStatus,
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
      updateServices({
        vectorDB: {
          available: false,
          status: 'offline',
          chunks: 0,
        },
        knowledgeGraph: {
          available: false,
          status: 'offline',
          entities: 0,
          relationships: 0,
        },
      });
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    checkServices();
  }, []);

  const vectorTone = getServiceTone(services.vectorDB.status);
  const graphTone = getServiceTone(services.knowledgeGraph.status);

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
                vectorTone.dotClass
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
                graphTone.dotClass
              }`}
            ></div>
            Graph Service
          </span>
          <span className="text-white font-mono font-medium">
            {graphTone.label}
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
