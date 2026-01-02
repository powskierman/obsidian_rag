import React, { useState } from 'react';
import { Download, Trash2, ChevronLeft, ChevronRight } from 'lucide-react';
import { useApp } from '../context/AppContext';

export default function ChatSidebar() {
    const {
        searchMode,
        llmProvider, setLLMProvider,
        settings, updateSettings,
        clearMessages,
        services,
        chatHistory,
        loadChatFromHistory,
        messages,
        saveChatToHistory
    } = useApp();

    const [isCollapsed, setIsCollapsed] = useState(false);

    const handleClear = () => {
        if (messages.length > 0) {
            saveChatToHistory();
        }
        clearMessages();
    };

    const handleExport = () => {
        if (messages.length === 0) return;

        // Generate markdown content
        const timestamp = new Date().toLocaleString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });

        const searchModeLabel = searchMode.charAt(0).toUpperCase() + searchMode.slice(1);

        let markdown = `# Obsidian RAG Conversation\n`;
        markdown += `**Date:** ${timestamp}\n`;
        markdown += `**Search Mode:** ${searchModeLabel}\n`;
        markdown += `**Model:** ${settings?.model || llmProvider}\n`;
        markdown += `\n---\n\n`;

        // Add all messages
        messages.forEach((msg, idx) => {
            if (idx > 0) markdown += `\n---\n\n`;

            markdown += `## ${msg.role === 'user' ? 'User' : 'Assistant'}\n`;
            markdown += `${msg.content}\n`;

            // Add sources if available
            if (msg.sources && msg.sources.length > 0) {
                markdown += `\n**Sources:**\n`;
                msg.sources.forEach((source, sourceIdx) => {
                    markdown += `${sourceIdx + 1}. ${source.filename} (${Math.round(source.relevance)}% relevance)\n`;
                    if (source.filepath) {
                        markdown += `   ${source.filepath}\n`;
                    }
                });
            }
        });

        // Create and download file
        const blob = new Blob([markdown], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;

        const filename = `obsidian-rag-chat-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.md`;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    // Collapsed view
    if (isCollapsed) {
        return (
            <div className="w-[70px] h-screen glass-panel flex flex-col flex-shrink-0 text-xs text-gray-200 p-2 gap-3 overflow-y-auto rounded-none border-r border-[#2C2C2E] relative z-20">
                {/* Expand Button */}
                <button
                    onClick={() => setIsCollapsed(false)}
                    className="w-full p-2 rounded-lg hover:bg-white/10 transition-colors flex items-center justify-center"
                    title="Expand sidebar"
                >
                    <ChevronRight size={20} className="text-white/60" />
                </button>

                {/* Logo */}
                <div className="w-full flex items-center justify-center mb-2">
                    <div className="w-10 h-10 rounded-xl bg-black/50 border border-white/10 flex items-center justify-center overflow-hidden shadow-lg shadow-purple-500/20">
                        <img src="/logo.png" alt="Obsidian RAG" className="w-full h-full object-cover" />
                    </div>
                </div>

                {/* Search Parameters - Compact */}
                <div className="space-y-3 py-3 border-y border-white/10">
                    {/* Search Mode */}
                    <div className="flex flex-col items-center gap-1" title={`Mode: ${searchMode}`}>
                        <span className="text-[10px] text-white/40 uppercase tracking-wide">Mode</span>
                        <span className="text-[9px] font-mono text-accent-gold font-semibold text-center leading-tight">
                            {searchMode === 'hybrid' ? '⚡3' :
                             searchMode === 'vector' ? '🔮V' :
                             searchMode === 'notes' ? '🕸️N' :
                             searchMode === 'entities' ? '⚡E' :
                             searchMode === 'notes+vector' ? 'NV' :
                             searchMode === 'entities+vector' ? 'EV' :
                             searchMode === 'dual-graph' ? '2G' : searchMode.slice(0, 3).toUpperCase()}
                        </span>
                    </div>

                    {/* LLM Provider */}
                    <div className="flex flex-col items-center gap-1" title={`Provider: ${llmProvider}`}>
                        <span className="text-[10px] text-white/40 uppercase tracking-wide">LLM</span>
                        <span className="text-[9px] font-mono text-purple-400 font-semibold">
                            {llmProvider === 'ollama' ? 'OLL' : llmProvider === 'gemini' ? 'GEM' : 'CLA'}
                        </span>
                    </div>

                    {/* Deep Thinking */}
                    <div className="flex flex-col items-center gap-1" title={`Deep Thinking: ${settings?.deepThinking ? 'On' : 'Off'}`}>
                        <span className="text-[10px] text-white/40 uppercase tracking-wide">DT</span>
                        <div className={`w-2 h-2 rounded-full ${settings?.deepThinking ? 'bg-accent-gold' : 'bg-white/20'}`} />
                    </div>

                    {/* Enhanced Search */}
                    <div className="flex flex-col items-center gap-1" title={`Enhanced: ${settings?.enhancedSearch ? 'On' : 'Off'}`}>
                        <span className="text-[10px] text-white/40 uppercase tracking-wide">ES</span>
                        <div className={`w-2 h-2 rounded-full ${settings?.enhancedSearch ? 'bg-accent-gold' : 'bg-white/20'}`} />
                    </div>

                    {/* Temperature */}
                    <div className="flex flex-col items-center gap-1" title={`Temperature: ${settings?.temperature || 0.7}`}>
                        <span className="text-[10px] text-white/40 uppercase tracking-wide">T</span>
                        <span className="text-[9px] font-mono text-indigo-400 font-semibold">{settings?.temperature || 0.7}</span>
                    </div>

                    {/* Sources */}
                    <div className="flex flex-col items-center gap-1" title={`Sources: ${settings?.sources || 10}`}>
                        <span className="text-[10px] text-white/40 uppercase tracking-wide">S</span>
                        <span className="text-[9px] font-mono text-indigo-400 font-semibold">{settings?.sources || 10}</span>
                    </div>
                </div>

                {/* Action Icons */}
                <div className="mt-auto space-y-2 pt-2 border-t border-white/10">
                    <button
                        onClick={handleExport}
                        disabled={messages.length === 0}
                        className="w-full p-2 rounded-lg hover:bg-white/10 transition-colors flex items-center justify-center disabled:opacity-30"
                        title="Export chat"
                    >
                        <Download size={16} className="text-white/60" />
                    </button>
                    <button
                        onClick={handleClear}
                        disabled={messages.length === 0}
                        className="w-full p-2 rounded-lg hover:bg-red-500/20 transition-colors flex items-center justify-center disabled:opacity-30"
                        title="Clear chat"
                    >
                        <Trash2 size={16} className="text-white/60" />
                    </button>
                </div>
            </div>
        );
    }

    // Full expanded view
    return (
        <div className="w-[280px] h-screen glass-panel flex flex-col flex-shrink-0 text-xs text-gray-200 p-4 gap-4 overflow-y-auto rounded-none border-r border-[#2C2C2E] relative z-20">
            {/* Header with Collapse Button */}
            <div className="flex flex-col items-center px-2 py-3 mb-6 relative">
                <button
                    onClick={() => setIsCollapsed(true)}
                    className="absolute top-0 right-0 p-1 rounded hover:bg-white/10 transition-colors"
                    title="Collapse sidebar"
                >
                    <ChevronLeft size={16} className="text-white/60" />
                </button>
                <div className="w-20 h-20 rounded-xl bg-black/50 border border-white/10 flex items-center justify-center overflow-hidden shadow-lg shadow-purple-500/20">
                    <img src="/logo.png" alt="Obsidian RAG" className="w-full h-full object-cover" />
                </div>
                <div className="flex items-center gap-1.5 mt-3">
                    <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                    <span className="text-[10px] font-medium text-gray-400">Online</span>
                </div>
            </div>

            {/* LLM Provider */}
            <div className="space-y-3">
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

                {/* Ollama Model Selector */}
                {llmProvider === 'ollama' && services.ollama.models.length > 0 && (
                    <div className="bg-white/5 p-2 rounded-lg border border-white/5">
                        <label className="text-[10px] text-gray-400 uppercase tracking-wide mb-1 block">Ollama Model</label>
                        <select
                            value={settings?.model || 'llama3.2:latest'}
                            onChange={(e) => updateSettings({ model: e.target.value })}
                            className="w-full bg-black/40 border border-white/10 rounded-md px-2 py-1.5 text-[11px] text-white focus:outline-none focus:ring-1 focus:ring-accent-gold/50"
                        >
                            {services.ollama.models.map((model) => (
                                <option key={model} value={model}>
                                    {model}
                                </option>
                            ))}
                        </select>
                    </div>
                )}
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
                <button
                    onClick={handleExport}
                    disabled={messages.length === 0}
                    className="flex-1 flex items-center justify-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 py-2 rounded-lg transition text-gray-300 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    <Download size={14} /> Export
                </button>
                <button
                    onClick={handleClear}
                    disabled={messages.length === 0}
                    className="flex-1 flex items-center justify-center gap-2 bg-white/5 hover:bg-red-500/20 border border-white/10 py-2 rounded-lg transition text-gray-300 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    <Trash2 size={14} /> Clear
                </button>
            </div>
        </div>
    );
}
