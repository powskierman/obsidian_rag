'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, ChevronLeft, ChevronRight, Database, Download, Play, RefreshCw, Settings2, Trash2, Wrench } from 'lucide-react';
import { useApp } from '../context/AppContext';

interface ChatSidebarProps {
    onVaultInfo?: () => void;
    onSettings?: () => void;
    onPrompt?: () => void;
    systemPromptActive?: boolean;
}

type DbKey = 'vector' | 'graph' | 'lightrag' | 'mempalace';
type IndexMode = 'partial' | 'full';

interface MaintenanceService {
    name: string;
    service: string;
    state: string;
    status: string;
    health: string;
    running: boolean;
    healthy: boolean;
}

const INDEX_DATABASES: Array<{ key: DbKey; label: string }> = [
    { key: 'vector', label: 'Vector' },
    { key: 'graph', label: 'NetworkX' },
    { key: 'lightrag', label: 'LightRAG' },
    { key: 'mempalace', label: 'MemPalace' },
];

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
    const [maintenanceOpen, setMaintenanceOpen] = useState(false);
    const [maintenanceLoading, setMaintenanceLoading] = useState(false);
    const [maintenanceError, setMaintenanceError] = useState<string | null>(null);
    const [maintenanceServices, setMaintenanceServices] = useState<MaintenanceService[]>([]);
    const [startingServices, setStartingServices] = useState(false);
    const [indexDatabases, setIndexDatabases] = useState<Set<DbKey>>(new Set(['vector']));
    const [indexMode, setIndexMode] = useState<IndexMode>('partial');
    const [indexRunning, setIndexRunning] = useState(false);
    const [indexOutput, setIndexOutput] = useState<string[]>([]);
    const [indexError, setIndexError] = useState<string | null>(null);
    const [indexExitCode, setIndexExitCode] = useState<number | null>(null);
    const indexPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

    const fetchMaintenanceStatus = useCallback(async () => {
        setMaintenanceLoading(true);
        setMaintenanceError(null);
        try {
            const res = await fetch('/api/maintenance');
            const data = await res.json();
            setMaintenanceServices(Array.isArray(data.services) ? data.services : []);
            if (!data.available && data.error) {
                setMaintenanceError(data.error);
            }
        } catch (error) {
            setMaintenanceError(error instanceof Error ? error.message : 'Maintenance check failed');
        } finally {
            setMaintenanceLoading(false);
        }
    }, []);

    const handleVerifyMaintenance = useCallback(async () => {
        await Promise.all([fetchMaintenanceStatus(), refreshServices()]);
    }, [fetchMaintenanceStatus, refreshServices]);

    const handleStartServices = useCallback(async () => {
        const targets = maintenanceServices
            .filter((service) => !service.running)
            .map((service) => service.service);
        setStartingServices(true);
        setMaintenanceError(null);
        try {
            const res = await fetch('/api/maintenance', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'start', services: targets.length > 0 ? targets : undefined }),
            });
            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.error || 'Failed to start services');
            }
            setMaintenanceServices(Array.isArray(data.statuses) ? data.statuses : []);
            await refreshServices();
        } catch (error) {
            setMaintenanceError(error instanceof Error ? error.message : 'Failed to start services');
        } finally {
            setStartingServices(false);
        }
    }, [maintenanceServices, refreshServices]);

    const stopIndexPolling = useCallback(() => {
        if (indexPollRef.current) {
            clearInterval(indexPollRef.current);
            indexPollRef.current = null;
        }
    }, []);

    const pollIndexStatus = useCallback(async () => {
        try {
            const res = await fetch('/api/index');
            if (!res.ok) return;
            const data = await res.json();
            setIndexOutput(data.output ?? []);
            setIndexError(data.error ?? null);
            setIndexExitCode(data.exitCode ?? null);
            if (!data.running) {
                setIndexRunning(false);
                stopIndexPolling();
                void refreshServices();
            }
        } catch {
            // Keep polling; transient route errors are common during dev reloads.
        }
    }, [refreshServices, stopIndexPolling]);

    const handleStartIndexing = useCallback(async () => {
        setIndexRunning(true);
        setIndexOutput([]);
        setIndexError(null);
        setIndexExitCode(null);
        try {
            const res = await fetch('/api/index', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    databases: Array.from(indexDatabases),
                    mode: indexMode,
                    lightragIncludeExtensions: ['.md'],
                }),
            });
            if (res.status === 409) {
                setIndexError('An indexing job is already running.');
                setIndexRunning(false);
                return;
            }
            if (!res.ok) {
                const text = await res.text();
                setIndexError(`Failed to start indexing: ${text}`);
                setIndexRunning(false);
                return;
            }
            stopIndexPolling();
            indexPollRef.current = setInterval(pollIndexStatus, 1500);
            void pollIndexStatus();
        } catch (error) {
            setIndexError(error instanceof Error ? error.message : 'Failed to start indexing');
            setIndexRunning(false);
        }
    }, [indexDatabases, indexMode, pollIndexStatus, stopIndexPolling]);

    useEffect(() => () => stopIndexPolling(), [stopIndexPolling]);

    const lightragCount = services.lightrag?.nodes
        ? (services.lightrag.nodes >= 1000
            ? `~${Math.round(services.lightrag.nodes / 1000)}k`
            : String(services.lightrag.nodes))
        : '—';

    const vectorCount = services.vectorDB.chunks > 0
        ? `v: ${services.vectorDB.chunks.toLocaleString()} chunks`
        : '—';

    const maintenanceHealthy = maintenanceServices.filter((service) => service.healthy).length;
    const maintenanceTotal = maintenanceServices.length;
    const stoppedServices = maintenanceServices.filter((service) => !service.running).length;
    const selectedIndexCount = indexDatabases.size;

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

                <div className="rounded-lg border border-white/[0.06] bg-white/[0.025]">
                    <button
                        onClick={() => {
                            const next = !maintenanceOpen;
                            setMaintenanceOpen(next);
                            if (next && maintenanceServices.length === 0) void fetchMaintenanceStatus();
                        }}
                        className="w-full flex items-center justify-between gap-3 px-3 py-2.5 text-left transition-colors hover:bg-white/[0.04]"
                    >
                        <span className="flex items-center gap-2 min-w-0">
                            <Wrench size={15} className="text-white/45 flex-shrink-0" />
                            <span className="text-[12px] font-medium text-white/65">Maintenance</span>
                        </span>
                        <span className="text-[10px] font-mono text-white/35">
                            {maintenanceTotal > 0 ? `${maintenanceHealthy}/${maintenanceTotal} healthy` : 'containers'}
                        </span>
                    </button>

                    {maintenanceOpen && (
                        <div className="border-t border-white/[0.06] px-3 py-3 space-y-3">
                            <div className="flex gap-2">
                                <button
                                    onClick={handleVerifyMaintenance}
                                    disabled={maintenanceLoading || isRefreshing}
                                    className="flex-1 flex items-center justify-center gap-1.5 rounded-md border border-white/[0.08] bg-white/[0.04] px-2 py-2 text-[11px] font-medium text-white/65 transition-colors hover:bg-white/[0.07] disabled:opacity-50"
                                >
                                    <RefreshCw size={13} className={maintenanceLoading || isRefreshing ? 'animate-spin' : ''} />
                                    Verify
                                </button>
                                <button
                                    onClick={handleStartServices}
                                    disabled={startingServices}
                                    className="flex-1 flex items-center justify-center gap-1.5 rounded-md border border-green-500/20 bg-green-500/10 px-2 py-2 text-[11px] font-medium text-green-200 transition-colors hover:bg-green-500/15 disabled:opacity-50"
                                >
                                    <Play size={13} />
                                    {stoppedServices > 0 ? `Start ${stoppedServices}` : 'Start all'}
                                </button>
                            </div>

                            {maintenanceError && (
                                <div className="flex gap-2 rounded-md border border-red-500/20 bg-red-500/10 px-2 py-2 text-[10px] leading-snug text-red-200">
                                    <AlertCircle size={13} className="mt-0.5 flex-shrink-0" />
                                    <span className="line-clamp-3">{maintenanceError}</span>
                                </div>
                            )}

                            {maintenanceServices.length > 0 && (
                                <div className="max-h-32 overflow-y-auto space-y-1 pr-1">
                                    {maintenanceServices.map((service) => (
                                        <div key={service.service} className="flex items-center justify-between gap-2 text-[10px]">
                                            <span className="flex items-center gap-1.5 min-w-0">
                                                <span
                                                    className={`inline-block h-1.5 w-1.5 rounded-full ${service.healthy ? 'bg-green-400' : service.running ? 'bg-yellow-400' : 'bg-red-400'}`}
                                                    style={{ boxShadow: `0 0 6px ${service.healthy ? '#4ade80' : service.running ? '#facc15' : '#f87171'}` }}
                                                />
                                                <span className="truncate text-white/45">{service.service}</span>
                                            </span>
                                            <span className="shrink-0 font-mono text-white/25">{service.health || service.state}</span>
                                        </div>
                                    ))}
                                </div>
                            )}

                            <div className="space-y-2">
                                <div className="flex items-center justify-between gap-2">
                                    <span className="text-[10px] font-semibold uppercase tracking-widest text-white/30">Vault Indexing</span>
                                    <div className="flex rounded-md border border-white/[0.08] bg-black/15 p-0.5">
                                        {(['partial', 'full'] as IndexMode[]).map((mode) => (
                                            <button
                                                key={mode}
                                                onClick={() => setIndexMode(mode)}
                                                disabled={indexRunning}
                                                className={`px-2 py-1 text-[10px] capitalize transition-colors rounded ${indexMode === mode ? 'bg-white/12 text-white/75' : 'text-white/35 hover:text-white/60'} disabled:opacity-50`}
                                            >
                                                {mode}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                <div className="grid grid-cols-2 gap-1.5">
                                    {INDEX_DATABASES.map(({ key, label }) => (
                                        <label
                                            key={key}
                                            className={`flex items-center gap-1.5 rounded-md border px-2 py-1.5 text-[10px] transition-colors ${indexDatabases.has(key) ? 'border-[#0A84FF]/30 bg-[#0A84FF]/10 text-white/70' : 'border-white/[0.06] bg-white/[0.02] text-white/35'} ${indexRunning ? 'opacity-50' : 'cursor-pointer hover:bg-white/[0.05]'}`}
                                        >
                                            <input
                                                type="checkbox"
                                                checked={indexDatabases.has(key)}
                                                disabled={indexRunning}
                                                onChange={() => {
                                                    const next = new Set(indexDatabases);
                                                    if (next.has(key)) next.delete(key);
                                                    else next.add(key);
                                                    setIndexDatabases(next);
                                                }}
                                                className="h-3 w-3 accent-[#0A84FF]"
                                            />
                                            <span className="truncate">{label}</span>
                                        </label>
                                    ))}
                                </div>

                                <button
                                    onClick={handleStartIndexing}
                                    disabled={indexRunning || selectedIndexCount === 0}
                                    className="w-full flex items-center justify-center gap-2 rounded-md border border-[#FFD60A]/25 bg-[#FFD60A]/10 px-2 py-2 text-[11px] font-semibold text-[#FFE680] transition-colors hover:bg-[#FFD60A]/15 disabled:opacity-50"
                                >
                                    {indexRunning ? (
                                        <RefreshCw size={13} className="animate-spin" />
                                    ) : (
                                        <Database size={13} />
                                    )}
                                    {indexRunning ? 'Indexing...' : `${indexMode === 'full' ? 'Full' : 'Partial'} index ${selectedIndexCount} DB${selectedIndexCount === 1 ? '' : 's'}`}
                                </button>

                                {(indexOutput.length > 0 || indexError || indexExitCode !== null) && (
                                    <div className="rounded-md border border-white/[0.06] bg-black/20 px-2 py-2 font-mono text-[10px] leading-relaxed text-white/35">
                                        <div className="mb-1 flex items-center justify-between">
                                            <span>index job</span>
                                            {indexExitCode !== null && (
                                                <span className={indexExitCode === 0 ? 'text-green-300' : 'text-red-300'}>
                                                    {indexExitCode === 0 ? <CheckCircle2 size={12} /> : `exit ${indexExitCode}`}
                                                </span>
                                            )}
                                        </div>
                                        {indexOutput.slice(-5).map((line, index) => (
                                            <div key={`${index}-${line}`} className="truncate">{line}</div>
                                        ))}
                                        {indexError && <div className="text-red-300">{indexError}</div>}
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>

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
