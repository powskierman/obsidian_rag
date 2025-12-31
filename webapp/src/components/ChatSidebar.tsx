import React from 'react';
import { Download, Trash2 } from 'lucide-react';
import { useApp } from '../context/AppContext';

export default function ChatSidebar() {
    const {
        searchMode, setSearchMode,
        llmProvider, setLLMProvider,
        settings, updateSettings,
        clearMessages,
        services,
        chatHistory,
        loadChatFromHistory
    } = useApp();

    return (
        <div className="w-[280px] h-screen glass-panel flex flex-col flex-shrink-0 text-xs text-gray-200 p-4 gap-4 overflow-y-auto rounded-none border-r border-[#2C2C2E] relative z-20">
            {/* Header */}
            <div className="flex items-center gap-3 px-2 py-3 mb-6">
                <div className="w-10 h-10 rounded-xl bg-black/50 border border-white/10 flex items-center justify-center overflow-hidden shadow-lg shadow-purple-500/20">
                    <img src="/logo.png" alt="Obsidian RAG" className="w-full h-full object-cover" />
                </div>
                <div>
                    <h1 className="font-bold text-white tracking-tight text-sm">OBSIDIAN <span className="text-[#00ffd5]">RAG</span></h1>
                    <div className="flex items-center gap-1.5 mt-0.5">
                        <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                        <span className="text-[10px] font-medium text-gray-400">Online</span>
                    </div>
                </div>
            </div>

            {/* Mode & Provider */}
            <div className="space-y-3">
                <div className="bg-black/20 p-1 rounded-lg flex">
                    {['vector', 'graph', 'hybrid'].map((mode) => (
                        <button
                            key={mode}
                            onClick={() => setSearchMode(mode as any)}
                            className={`flex-1 py-1.5 rounded-md text-[11px] font-medium transition-all ${searchMode === mode ? 'bg-accent-gold text-black shadow-sm' : 'text-gray-400 hover:text-gray-200'}`}
                        >
                            {mode.charAt(0).toUpperCase() + mode.slice(1)}
                        </button>
                    ))}
                </div>
                <div className="bg-black/20 p-1 rounded-lg flex">
                    {['Ollama', 'Gemini', 'Claude'].map((llm) => (
                        <button
                            key={llm}
                            onClick={() => setLLMProvider(llm.toLowerCase() as any)}
                            className={`flex-1 py-1.5 rounded-md text-[11px] font-medium transition-all ${llmProvider === llm.toLowerCase() ? 'bg-accent-gold text-black shadow-sm' : 'text-gray-400 hover:text-gray-200'}`}
                        >
                            {llm}
                        </button>
                    ))}
                </div>
            </div>

            {/* Toggles */}
            <div className="space-y-2 bg-white/5 p-3 rounded-xl border border-white/5">
                <div className="flex items-center justify-between">
                    <span className="text-gray-300">Enhanced Search</span>
                    <button
                        onClick={() => updateSettings({ enhancedSearch: !settings?.enhancedSearch })}
                        className={`w-8 h-4 rounded-full transition-colors relative ${settings?.enhancedSearch ? 'bg-accent-gold' : 'bg-white/10'}`}
                    >
                        <div className={`w-3 h-3 rounded-full bg-white absolute top-0.5 transition-all ${settings?.enhancedSearch ? 'left-4.5' : 'left-0.5'}`} />
                    </button>
                </div>
                <div className="flex items-center justify-between">
                    <span className="text-gray-300">Deep Thinking</span>
                    <button
                        onClick={() => updateSettings({ deepThinking: !settings?.deepThinking })}
                        className={`w-8 h-4 rounded-full transition-colors relative ${settings?.deepThinking ? 'bg-accent-gold' : 'bg-white/10'}`}
                    >
                        <div className={`w-3 h-3 rounded-full bg-white absolute top-0.5 transition-all ${settings?.deepThinking ? 'left-4.5' : 'left-0.5'}`} />
                    </button>
                </div>
            </div>

            {/* Status Ribbon */}
            <div className="flex justify-between items-center px-2 py-2 border-y border-white/10 text-[10px] text-accent-gold font-mono">
                <span>📂 {services.vectorDB.chunks > 1000 ? `${(services.vectorDB.chunks / 1000).toFixed(1)}k` : services.vectorDB.chunks} Chunks</span>
                <span>🕸️ {services.knowledgeGraph.entities > 1000 ? `${(services.knowledgeGraph.entities / 1000).toFixed(1)}k` : services.knowledgeGraph.entities} Entities</span>
            </div>

            {/* Settings Grid */}
            <div className="space-y-4">
                <div className="space-y-2">
                    <div className="flex justify-between text-[11px] text-gray-300">
                        <span>Sources</span>
                        <span className="text-accent-gold font-mono">{settings?.sources || 10}</span>
                    </div>
                    <input
                        type="range"
                        min="1"
                        max="50"
                        value={settings?.sources || 10}
                        onChange={(e) => updateSettings({ sources: parseInt(e.target.value) })}
                        className="slider"
                    />
                </div>

                <div className="space-y-2">
                    <div className="flex justify-between text-[11px] text-gray-300">
                        <span>Temperature</span>
                        <span className="text-accent-gold font-mono">{settings?.temperature || 0.7}</span>
                    </div>
                    <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.01"
                        value={settings?.temperature || 0.7}
                        onChange={(e) => updateSettings({ temperature: parseFloat(e.target.value) })}
                        className="slider"
                    />
                </div>
            </div>

            {/* History List */}
            <div className="flex-1 overflow-hidden flex flex-col min-h-0 pt-2 border-t border-white/10">
                <h3 className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold mb-2 px-1">Recent Chats</h3>
                <div className="flex-1 overflow-y-auto space-y-1 pr-1">
                    {chatHistory.length === 0 ? (
                        <div className="text-gray-600 italic px-2 py-4 text-center">No history yet</div>
                    ) : (
                        chatHistory.map((item) => (
                            <button
                                key={item.id}
                                onClick={() => loadChatFromHistory(item.id)}
                                className="w-full text-left p-2 rounded-lg hover:bg-white/5 transition-colors group"
                            >
                                <div className="text-gray-300 truncate font-medium group-hover:text-white transition-colors">{item.firstMessage}</div>
                                <div className="flex justify-between text-[10px] text-gray-500 mt-1">
                                    <span>{new Date(item.timestamp).toLocaleDateString()}</span>
                                    <span className="capitalize">{item.searchMode}</span>
                                </div>
                            </button>
                        ))
                    )}
                </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3 pt-2 mt-auto border-t border-white/10">
                <button className="flex-1 flex items-center justify-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 py-2 rounded-lg transition text-gray-300 font-medium">
                    <Download size={14} /> Export
                </button>
                <button
                    onClick={clearMessages}
                    className="flex-1 flex items-center justify-center gap-2 bg-white/5 hover:bg-red-500/20 border border-white/10 py-2 rounded-lg transition text-gray-300 font-medium"
                >
                    <Trash2 size={14} /> Clear
                </button>
            </div>
        </div>
    );
}
