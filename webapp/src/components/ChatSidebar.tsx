'use client';

import React, { useState } from 'react';
import { Download, Trash2, ChevronLeft, ChevronRight, Database, Settings2, RefreshCw } from 'lucide-react';
import { useApp } from '../context/AppContext';

interface ChatSidebarProps {
    onVaultInfo?: () => void;
    onSettings?: () => void;
    onPrompt?: () => void;
    systemPromptActive?: boolean;
}

export default function ChatSidebar({ onVaultInfo, onSettings, onPrompt, systemPromptActive }: ChatSidebarProps) {
    const {
        searchMode,
        settings,
        clearMessages,
        services,
        chatHistory,
        loadChatFromHistory,
        messages,
        saveChatToHistory,
        refreshServices,
    } = useApp();

    const [isCollapsed, setIsCollapsed] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);

    const handleClear = () => {
        if (messages.length > 0) saveChatToHistory();
        clearMessages();
    };

    const handleExport = () => {
        if (messages.length === 0) return;
        const timestamp = new Date().toLocaleString('en-US', { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        let markdown = `# Obsidian RAG Conversation\n**Date:** ${timestamp}\n**Search Mode:** ${searchMode}\n**Model:** ${settings?.model}\n\n---\n\n`;
        messages.forEach((msg, idx) => {
            if (idx > 0) markdown += `\n---\n\n`;
            markdown += `## ${msg.role === 'user' ? 'User' : 'Assistant'}\n${msg.content}\n`;
            if (msg.sources && msg.sources.length > 0) {
                markdown += `\n**Sources:**\n`;
                msg.sources.forEach((s, si) => {
                    markdown += `${si + 1}. ${s.filename} (${Math.round(s.relevance)}%)\n`;
                    if (s.filepath) markdown += `   ${s.filepath}\n`;
                });
            }
        });
        const blob = new Blob([markdown], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `obsidian-rag-chat-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const handleRefreshServices = async () => {
        setIsRefreshing(true);
        try {
            await refreshServices();
        } finally {
            setIsRefreshing(false);
        }
    };

    const lightragCount = services.lightrag?.nodes
        ? (services.lightrag.nodes >= 1000
            ? `~${Math.round(services.lightrag.nodes / 1000)}k`
            : String(services.lightrag.nodes))
        : '—';

    const vectorCount = services.vectorDB.chunks > 0
        ? `v: ${services.vectorDB.chunks.toLocaleString()} chunks`
        : '—';

    // ── Collapsed ──────────────────────────────────────────────────────
    if (isCollapsed) {
        return (
            <div className="sidebar-glass w-[58px] h-full flex flex-col flex-shrink-0 items-center py-3 gap-3">
                <button
                    onClick={() => setIsCollapsed(false)}
                    className="p-2 rounded-lg hover:bg-white/10 transition-colors"
                    title="Expand sidebar"
                >
                    <ChevronRight size={18} className="text-white/50" />
                </button>
                <div className="flex-1" />
                {onVaultInfo && (
                    <button onClick={onVaultInfo} className="p-2 rounded-lg hover:bg-white/10 transition-colors" title="Vault Information">
                        <Database size={16} className="text-white/40" />
                    </button>
                )}
                {onSettings && (
                    <button onClick={onSettings} className="p-2 rounded-lg hover:bg-white/10 transition-colors" title="Settings">
                        <Settings2 size={16} className="text-white/40" />
                    </button>
                )}
                <button
                    onClick={handleRefreshServices}
                    disabled={isRefreshing}
                    className="p-2 rounded-lg hover:bg-white/10 transition-colors disabled:opacity-50"
                    title="Refresh services"
                >
                    <RefreshCw size={16} className={`text-white/40 ${isRefreshing ? 'animate-spin' : ''}`} />
                </button>
            </div>
        );
    }

    // ── Expanded ───────────────────────────────────────────────────────
    return (
        <div className="sidebar-glass w-[392px] h-full flex flex-col flex-shrink-0 overflow-hidden">

            {/* Brand */}
            <div className="flex items-center justify-between px-8 pt-9 pb-8 flex-shrink-0">
                <span className="text-[27px] font-semibold text-white tracking-tight">
                    Obsidian.Brain
                </span>
                <button
                    onClick={() => setIsCollapsed(true)}
                    className="p-1 rounded hover:bg-white/10 transition-colors"
                    title="Collapse sidebar"
                >
                    <ChevronLeft size={16} className="text-white/40" />
                </button>
            </div>

            <div className="mx-4 border-t border-white/[0.06]" />

            {/* Primary controls */}
            <div className="px-4 py-4 flex-shrink-0 space-y-2">
                {onSettings && (
                    <button
                        onClick={onSettings}
                        className="w-full flex items-center gap-3 rounded-xl border border-[#FFD60A]/35 bg-[#FFD60A]/10 px-3.5 py-3 text-left shadow-[0_0_24px_rgba(255,214,10,0.08)] transition-colors hover:border-[#FFD60A]/55 hover:bg-[#FFD60A]/15 group"
                    >
                        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#FFD60A] text-black flex-shrink-0">
                            <Settings2 size={18} />
                        </span>
                        <span className="min-w-0">
                            <span className="block text-sm font-semibold text-white">Settings</span>
                            <span className="block truncate text-[11px] text-white/45 group-hover:text-white/60">
                                Model, retrieval, sources, indexing
                            </span>
                        </span>
                    </button>
                )}

                <button
                    onClick={handleRefreshServices}
                    disabled={isRefreshing}
                    className="w-full flex items-center gap-3 rounded-lg border border-[#0A84FF]/25 bg-[#0A84FF]/10 px-3 py-2.5 text-left transition-colors hover:border-[#0A84FF]/45 hover:bg-[#0A84FF]/15 disabled:opacity-60"
                >
                    <RefreshCw size={16} className={`text-[#64AFFF] flex-shrink-0 ${isRefreshing ? 'animate-spin' : ''}`} />
                    <span className="text-[12px] font-medium text-white/70">
                        {isRefreshing ? 'Refreshing services...' : 'Refresh services'}
                    </span>
                </button>

                <div className="grid grid-cols-2 gap-2">
                    {onVaultInfo && (
                        <button
                            onClick={onVaultInfo}
                            className="flex items-center gap-2 rounded-lg border border-white/[0.06] bg-white/[0.03] px-2.5 py-2 hover:bg-white/[0.06] transition-colors group"
                        >
                            <Database size={14} className="text-white/35 group-hover:text-white/60 transition-colors flex-shrink-0" />
                            <span className="truncate text-[12px] text-white/55 group-hover:text-white/75 transition-colors">Vault</span>
                        </button>
                    )}
                    {onPrompt && (
                        <button
                            onClick={onPrompt}
                            className="flex items-center gap-2 rounded-lg border border-white/[0.06] bg-white/[0.03] px-2.5 py-2 hover:bg-white/[0.06] transition-colors group"
                        >
                            <svg className="text-white/35 group-hover:text-white/60 transition-colors flex-shrink-0" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
                            </svg>
                            <span className="truncate text-[12px] text-white/55 group-hover:text-white/75 transition-colors">
                                Prompt {systemPromptActive && <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#0A84FF] ml-1 align-middle" />}
                            </span>
                        </button>
                    )}
                </div>
            </div>

            <div className="mx-4 border-t border-white/[0.06]" />

            {/* Recent Chats */}
            <div className="flex-1 flex flex-col min-h-0 px-3 pt-3">
                <div className="flex items-center justify-between mb-2 px-1">
                    <span className="text-[10px] font-semibold uppercase tracking-widest text-white/30">Recent Chats</span>
                    <div className="flex gap-1">
                        <button
                            onClick={handleExport}
                            disabled={messages.length === 0}
                            className="p-1 rounded hover:bg-white/10 transition-colors disabled:opacity-30"
                            title="Export chat"
                        >
                            <Download size={12} className="text-white/50" />
                        </button>
                        <button
                            onClick={handleClear}
                            disabled={messages.length === 0}
                            className="p-1 rounded hover:bg-red-500/20 transition-colors disabled:opacity-30"
                            title="Clear chat"
                        >
                            <Trash2 size={12} className="text-white/50" />
                        </button>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto space-y-0.5 pr-0.5">
                    {chatHistory.length === 0 ? (
                        <div className="text-[11px] text-white/20 italic px-2 py-3">No history yet</div>
                    ) : (
                        chatHistory.map((item) => {
                            const age = Date.now() - new Date(item.timestamp).getTime();
                            const ageLabel = age < 60 * 60 * 1000
                                ? `${Math.round(age / 60000)}m`
                                : age < 24 * 60 * 60 * 1000
                                    ? `${Math.round(age / 3600000)}h`
                                    : new Date(item.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

                            return (
                                <button
                                    key={item.id}
                                    onClick={() => loadChatFromHistory(item.id)}
                                    className="w-full text-left flex items-start gap-2 px-2 py-2 rounded-lg hover:bg-white/[0.05] transition-colors group"
                                >
                                    <svg className="text-white/20 mt-0.5 flex-shrink-0" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                                    </svg>
                                    <span className="flex-1 text-[12px] text-white/60 group-hover:text-white/80 truncate transition-colors leading-tight">
                                        {item.firstMessage}
                                    </span>
                                    <span className="text-[10px] text-white/25 flex-shrink-0">{ageLabel}</span>
                                </button>
                            );
                        })
                    )}
                </div>
            </div>

            <div className="mx-4 border-t border-white/[0.06] mt-2" />

            {/* Service status */}
            <div className="px-4 py-3 flex-shrink-0 space-y-1.5">
                <div className="pb-1 text-[10px] font-semibold uppercase tracking-widest text-white/30">Services</div>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-400" style={{ boxShadow: '0 0 6px #4ade80' }} />
                        <span className="text-[10px] font-mono text-white/30 tracking-wider">BRAIN_ONLINE</span>
                    </div>
                    <span className="text-[10px] font-mono text-white/20">{vectorCount}</span>
                </div>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-purple-400" style={{ boxShadow: '0 0 6px #c084fc' }} />
                        <span className="text-[10px] font-mono text-white/30 tracking-wider">LIGHTRAG</span>
                    </div>
                    <span className="text-[10px] font-mono text-white/20">{lightragCount}</span>
                </div>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                        <span className={`inline-block w-1.5 h-1.5 rounded-full ${services.knowledgeGraph.status === 'online' ? 'bg-indigo-400' : 'bg-red-400'}`}
                            style={{ boxShadow: services.knowledgeGraph.status === 'online' ? '0 0 6px #818cf8' : '0 0 6px #f87171' }} />
                        <span className="text-[10px] font-mono text-white/30 tracking-wider">NETWORKX</span>
                    </div>
                    <span className="text-[10px] font-mono text-white/20">
                        {services.knowledgeGraph.status === 'online' ? 'G: Online' : 'Offline'}
                    </span>
                </div>
            </div>
        </div>
    );
}
