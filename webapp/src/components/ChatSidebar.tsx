import React, { useState } from 'react';
import { Download, Trash2, ChevronLeft, ChevronRight } from 'lucide-react';
import { useApp } from '../context/AppContext';

export default function ChatSidebar() {
    const {
        searchMode,
        llmProvider,
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


                <div className="space-y-3 py-3 border-y border-white/10">
                    {/* Compact History Indicator */}
                    <div className="flex flex-col items-center gap-1 text-center" title="Chat History">
                        <span className="text-[10px] text-white/40 uppercase tracking-wide">History</span>
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
        <div className="w-[280px] h-screen glass-panel flex flex-col flex-shrink-0 text-xs text-gray-200 p-4 gap-3 overflow-y-auto rounded-none border-r border-[#2C2C2E] relative z-20">
            {/* Header with Collapse Button */}
            <div className="flex items-center justify-between px-2 py-1 mb-2 relative">
                <div className="flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-green-500" />
                    <span className="text-[10px] font-medium text-gray-400 font-mono tracking-wider">BRAIN_ONLINE</span>
                </div>
                <button
                    onClick={() => setIsCollapsed(true)}
                    className="p-1 rounded hover:bg-white/10 transition-colors"
                    title="Collapse sidebar"
                >
                    <ChevronLeft size={16} className="text-white/60" />
                </button>
            </div>


            {/* History List - Takes remaining space */}
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
            <div className="flex gap-2 pt-2 mt-auto border-t border-white/10">
                <button
                    onClick={handleExport}
                    disabled={messages.length === 0}
                    className="flex-1 flex items-center justify-center gap-1.5 bg-white/5 hover:bg-white/10 border border-white/10 py-1.5 rounded-lg transition text-gray-300 text-[11px] font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    <Download size={12} /> Export
                </button>
                <button
                    onClick={handleClear}
                    disabled={messages.length === 0}
                    className="flex-1 flex items-center justify-center gap-1.5 bg-white/5 hover:bg-red-500/20 border border-white/10 py-1.5 rounded-lg transition text-gray-300 text-[11px] font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    <Trash2 size={12} /> Clear
                </button>
            </div>

        </div>
    );
}
