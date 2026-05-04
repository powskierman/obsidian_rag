'use client';

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { RefreshCw, Search, Sparkles } from 'lucide-react';
import ChatSidebar from '../components/ChatSidebar';
import ThinkingIndicator from '../components/ThinkingIndicator';
import PromptModal from '../components/PromptModal';
import VaultInfoModal from '../components/VaultInfoModal';
import SettingsPanelModal from '../components/sidebar/SettingsPanelModal';
import ForceGraph from '../components/ForceGraph';
import SourcesDisplay from '../components/chat/SourcesDisplay';
import RatingButtons from '../components/chat/RatingButtons';
import { api } from '../lib/api';
import { useApp } from '../context/AppContext';
import { EnhancedSearchData, SearchMode, Source } from '../lib/types';

const SEARCH_MODE_LABELS: Record<SearchMode, string> = {
    ask:        'Ask',
    research:   'Research',
    investigate:'Investigate',
};

const VAULT_PROMPT_POOL = [
    'Summarize my lymphoma treatment timeline',
    'Connect Yescarta, CAR-T therapy, and lymphoma in my notes',
    'Find my notes about Apple Watch and Home Assistant',
    'What do my notes say about PET scan results and SUV changes?',
    'Summarize my LightRAG indexing and search quality notes',
    'Find notes about LM Studio, MLX, and local model setup',
    'Show my movie catalog notes from Apple and NAS sources',
    'Find recipes involving carbonated water',
    'What troubleshooting notes mention memory_context?',
    'Summarize my Obsidian vault architecture notes',
    'Find notes about MCP path resolution and vault access',
    'Connect lymphoma prognosis, novel agents, and treatment logs',
];

const rotateSuggestedPrompts = (current: string[] = []): string[] => {
    const available = VAULT_PROMPT_POOL.filter((prompt) => !current.includes(prompt));
    const source = available.length >= 3 ? available : VAULT_PROMPT_POOL;
    const shuffled = [...source].sort(() => Math.random() - 0.5);
    return shuffled.slice(0, 3);
};

// Auto-routing to vault_review is now handled backend-side (depth='auto').
// The frontend no longer needs to classify queries or resolve backend modes.

const normalizeDeepThinkingSource = (source: any): Source => {
    const filepath = source?.filepath || source?.file_path || source?.url || '';
    const filename = source?.filename || source?.title || (typeof filepath === 'string' ? filepath.split('/').pop() : '') || 'Unknown';
    const rawRelevance = source?.relevance;
    const relevance = Number.isFinite(rawRelevance)
        ? Number(rawRelevance)
        : Number.isFinite(Number(rawRelevance))
            ? Number(rawRelevance)
            : 50;

    return {
        filename,
        filepath: filepath || filename,
        relevance,
        snippet: source?.snippet || source?.content || '',
        sourceType: source?.sourceType || source?.source_type,
        sourceCategory: source?.sourceCategory || source?.source_category,
    };
};

const mapDeepThinkingCitations = (rawCitations: any): Source[] => {
    const flatCitations = Array.isArray(rawCitations) ? rawCitations.flat() : [rawCitations];

    return flatCitations
        .filter(Boolean)
        .map((cit: any) => {
            const citStr = typeof cit === 'string' ? cit : JSON.stringify(cit);

            if (citStr.includes('[[') && citStr.includes(']]')) {
                const match = citStr.match(/\[\[(.*?)\]\]/);
                const inner = match ? match[1] : citStr;
                return {
                    filename: inner.split('/').pop() || inner,
                    filepath: inner,
                    relevance: 95,
                    snippet: 'Cited via research reasoning.',
                    sourceCategory: 'vault' as const,
                };
            }

            const mdLinkMatch = citStr.match(/\[(.*?)\]\((.*?)\)/);
            if (mdLinkMatch) {
                return {
                    filename: mdLinkMatch[1],
                    filepath: mdLinkMatch[2],
                    relevance: 90,
                    snippet: 'Retrieved during research.',
                    sourceType: 'web-result' as const,
                    sourceCategory: 'web' as const,
                };
            }

            if (citStr.startsWith('http')) {
                return {
                    filename: citStr,
                    filepath: citStr,
                    relevance: 85,
                    snippet: citStr,
                    sourceType: 'web-result' as const,
                    sourceCategory: 'web' as const,
                };
            }

            if (citStr.startsWith('[') && citStr.endsWith(']')) {
                const inner = citStr.substring(1, citStr.length - 1);
                return {
                    filename: inner.split('/').pop() || inner,
                    filepath: inner,
                    relevance: 90,
                    snippet: 'Identified during analysis.',
                    sourceCategory: 'vault' as const,
                };
            }

            return {
                filename: citStr,
                filepath: citStr,
                relevance: 80,
                snippet: 'Retrieved during research.',
                sourceCategory: citStr.startsWith('http') ? 'web' : 'vault',
            };
        });
};

const formatThinkingLog = (data: any): string => {
    const base = data.content || data.message || '';
    const details = data.details;
    if (!details || typeof details !== 'object') {
        return base;
    }

    const detailMessage = details.error || details.reason || details.message;
    if (!detailMessage || typeof detailMessage !== 'string') {
        return base;
    }

    return base ? `${base}: ${detailMessage}` : detailMessage;
};

const appendRetrievalWarnings = (answer: string, warnings: any): string => {
    const warningList = Array.isArray(warnings)
        ? warnings.filter((warning) => typeof warning === 'string' && warning.trim())
        : [];

    if (warningList.length === 0) {
        return answer;
    }

    return `${answer}\n\n---\n\n### Retrieval Warnings\n${warningList.map((warning) => `- ${warning}`).join('\n')}`;
};

const mapWebResultsToSources = (webSearch: any): Source[] => {
    const results = Array.isArray(webSearch?.results) ? webSearch.results : [];
    return results
        .filter((result: any) => result && typeof result === 'object')
        .map((result: any, index: number) => ({
            filename: String(result.title || result.url || `Web result ${index + 1}`),
            filepath: String(result.url || ''),
            relevance: Math.max(5, 30 - (index * 2)),
            snippet: String(result.content || result.snippet || ''),
            sourceType: 'web-result' as const,
            sourceCategory: 'web' as const,
        }));
};

const formatDeepThinkingError = (data: any): string => {
    if (data?.code === 'MLX_RECOVERING') {
        return 'Error: Local LM Studio provider became unavailable; recovery running. Retry in 15-30 seconds.';
    }

    const rawContent = typeof data?.content === 'string' ? data.content : '';
    const lowered = rawContent.toLowerCase();
    const mlxTransportMarkers = [
        'remotedisconnected',
        'remote end closed connection',
        'connection aborted',
        'max retries exceeded',
        'host.docker.internal',
        '/v1/chat/completions',
        'connection refused',
        'insufficient memory',
        '[metal]',
    ];
    if (mlxTransportMarkers.some((marker) => lowered.includes(marker))) {
        return 'Error: Local LM Studio provider became unavailable; recovery running. Retry in 15-30 seconds.';
    }

    if (typeof data?.content === 'string' && data.content.trim()) {
        return `Error: ${data.content}`;
    }

    return 'Error: Deep Thinking request failed.';
};

export default function Home() {
    console.log('Home component rendering');

    const {
        messages,
        addMessage,
        setIsLoading,
        isLoading,
        searchMode,
        llmProvider,
        settings,
        systemPrompt,
        setSystemPrompt,
        setSearchMode,
        services,
    } = useApp();

    console.log('Home component state:', { messages, isLoading, searchMode });

    const [input, setInput] = useState('');
    const [isPromptModalOpen, setIsPromptModalOpen] = useState(false);
    const [isVaultModalOpen, setIsVaultModalOpen] = useState(false);
    const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
    const [thinkingLog, setThinkingLog] = useState<string>('');
    const [graphData, setGraphData] = useState<{ nodes: any[], links: any[] } | null>(null);
    const [showGraph, setShowGraph] = useState(false);
    const [suggestedPrompts, setSuggestedPrompts] = useState<string[]>(() => VAULT_PROMPT_POOL.slice(0, 3));
    const modeLabel = SEARCH_MODE_LABELS[searchMode] || searchMode;
    const isDeepThinkingMode = searchMode === 'investigate';
    const handleSendMessage = async () => {
        if (!input.trim() || isLoading) return;

        const userMsg = input;
        const queryId = Date.now().toString();
        setInput('');
        setThinkingLog('');
        setShowGraph(false);

        // Add user message
        addMessage({ role: 'user', content: userMsg });
        setIsLoading(true);

        try {
            // Deep Thinking Mode (WebSocket)
            if (isDeepThinkingMode) {
                const ws = new WebSocket(api.deepResearchEndpoint);

                ws.onopen = () => {
                    // Send query AND selected provider
                    ws.send(JSON.stringify({
                        query: userMsg,
                        provider: llmProvider,
                        model: (llmProvider === 'openrouter' || llmProvider === 'chatgpt' || llmProvider === 'lmstudio') ? settings.model : undefined,
                        max_sources: settings.sources,
                    }));
                };

                ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);

                        if (data.type === 'log' || data.type === 'status') {
                            setThinkingLog(formatThinkingLog(data));
                        } else if (data.type === 'result') {
                            // Final result received
                            const answer = data.data?.answer || data.markdown || data.content;
                            if (answer) {
                                const backendSources = Array.isArray(data.data?.sources)
                                    ? data.data.sources.map(normalizeDeepThinkingSource)
                                    : [];
                                const mappedSources: Source[] = backendSources.length > 0
                                    ? backendSources
                                    : mapDeepThinkingCitations(data.data?.citations || []);
                                const finalContent = appendRetrievalWarnings(answer, data.data?.warnings);

                                addMessage({
                                    role: 'assistant',
                                    content: finalContent,
                                    sources: settings.showSources ? mappedSources : undefined,
                                    queryId,
                                    timestamp: new Date().toISOString(),
                                });
                            } else {
                                console.error('No answer found in result:', data);
                                addMessage({
                                    role: 'assistant',
                                    content: 'Error: Received result but no answer content found.',
                                });
                            }
                            ws.close();
                            setIsLoading(false);
                            setThinkingLog('');
                        } else if (data.type === 'error') {
                            console.warn('Deep Thinking Error:', data.content);
                            if (data.code === 'MLX_RECOVERING') {
                                setThinkingLog('LM Studio local model became unavailable; recovery running.');
                            }
                            addMessage({
                                role: 'assistant',
                                content: formatDeepThinkingError(data),
                            });
                            ws.close();
                            setIsLoading(false);
                            setThinkingLog('');
                        }
                    } catch (e) {
                        console.error('WebSocket parse error:', e);
                    }
                };

                ws.onerror = (error) => {
                    console.error('WebSocket Error:', error);
                    addMessage({
                        role: 'assistant',
                        content: "Error: WebSocket connection failed.",
                    });
                    setIsLoading(false);
                    setThinkingLog('');
                };

                // Safety timeout
                setTimeout(() => {
                    if (ws.readyState === WebSocket.OPEN) {
                        // Optional: close or warn
                    }
                }, 300000);

            } else {
                // Standard Unified Search (HTTP) — canonical mode names
                const modelToUse = llmProvider === 'ollama' || llmProvider === 'openrouter' || llmProvider === 'chatgpt' || llmProvider === 'lmstudio' ? settings.model : '';

                console.log('📡 Sending query settings:', {
                    mode: searchMode,
                    depth: settings.researchDepth,
                    dataSources: settings.dataSources,
                    sources: settings.sources,
                    relevanceThreshold: settings.relevanceThreshold,
                });
                const result = await api.unifiedSearch(
                    userMsg,
                    searchMode === 'ask' ? 'ask' : 'research',
                    settings.sources,
                    llmProvider,
                    modelToUse,
                    settings.temperature,
                    settings.relevanceThreshold,
                    settings.enhancedSearch,
                    settings.briefConceptIndex,
                    systemPrompt,
                    settings.researchDepth ?? 'auto',
                    settings.dataSources ?? ['vault'],
                    settings.pdfTree,
                );

                let answer = result.answer;
                const vaultSources: Source[] = result.sources || [];
                const webSources: Source[] = settings.enhancedSearch ? mapWebResultsToSources(result.web_search) : [];
                const sources: Source[] = [...vaultSources, ...webSources];
                const enhancedSearchData: EnhancedSearchData | undefined = settings.enhancedSearch
                    ? {
                        llmKnowledge: typeof result.llm_knowledge === 'string'
                            ? result.llm_knowledge
                            : result.llm_knowledge ? JSON.stringify(result.llm_knowledge) : undefined,
                        webResults: Array.isArray(result.web_search?.results) ? result.web_search.results : [],
                        webSearchTerms: result.web_search?.search_terms || '',
                        webStatus: result.web_search?.message || result.web_search?.error || '',
                    }
                    : undefined;

                // Handle Graph Visualization
                if (result.extracted_entities && result.extracted_entities.length > 0) {
                    const nodes = result.extracted_entities.map((entity: any) => ({
                        id: typeof entity === 'string' ? entity : entity.name,
                        name: typeof entity === 'string' ? entity : entity.name,
                        val: typeof entity === 'string' ? 5 : (entity.connections || 5),
                        color: '#4facfe'
                    }));

                    // Add a central node for the query to cluster results around it
                    const queryNodeId = "Query";
                    // Avoid duplicate if query node name overlaps with entity
                    const safeNodes = nodes.filter((n: any) => n.id !== queryNodeId);

                    safeNodes.push({ id: queryNodeId, name: userMsg, val: 10, color: '#ffffff' });

                    const links = [];
                    // Connect everything to the central query node
                    for (const node of safeNodes) {
                        if (node.id !== queryNodeId) {
                            // Calculate distance based on relevance
                            // Heuristic: If entity name matches any source text, use that source's relevance
                            // High relevance (1.0) -> Short distance (50)
                            // Low relevance (0.0) -> Long distance (200)

                            let maxRelevance = 0;
                            const normalize = (str: string) => str.toLowerCase().replace(/[^a-z0-9]/g, '');
                            const nodeNameNorm = normalize(node.name);

                            if (sources && sources.length > 0) {
                                for (const src of sources) {
                                    // Check if entity appears in source snippet or filename
                                    if (normalize(src.snippet).includes(nodeNameNorm) || normalize(src.filename).includes(nodeNameNorm)) {
                                        if (src.relevance > maxRelevance) maxRelevance = src.relevance;
                                    }
                                }
                            }

                            // If no match found, default to moderate relevance (0.5) if it was extracted at all
                            // or just use a default base linkage. 
                            // Deep Thinking usually extracts highly relevant entities, so we can assume some relevance.
                            // But let's spread them out if we strictly don't know.

                            const relevance = maxRelevance > 0 ? maxRelevance : 0.3;
                            const distance = 200 - (relevance * 150); // 1.0 -> 50, 0.0 -> 200

                            links.push({
                                source: queryNodeId,
                                target: node.id,
                                distance: distance
                            });
                        }
                    }

                    setGraphData({ nodes: safeNodes, links });
                } else {
                    setGraphData(null);
                }

                addMessage({
                    role: 'assistant',
                    content: answer,
                    sources: settings.showSources ? sources : undefined,
                    enhancedSearch: enhancedSearchData,
                    retrievalIntent: result.retrievalIntent,
                    queryId,
                    timestamp: new Date().toISOString(),
                });
                setIsLoading(false);
            }

        } catch (error) {
            console.error('Query error:', error);
            addMessage({
                role: 'assistant',
                content: `Error: Could not retrieve answer. ${error instanceof Error ? error.message : 'Unknown error'}`,
            });
            setIsLoading(false);
        }
    };

    const lightragNodeLabel = services.lightrag?.nodes
        ? (services.lightrag.nodes >= 1000
            ? `~${Math.round(services.lightrag.nodes / 1000)}k`
            : String(services.lightrag.nodes))
        : '—';

    return (
        <div
            className="app-shell flex h-screen flex-col text-white font-sans overflow-hidden selection:bg-[#FFD60A] selection:text-black"
            style={{ position: 'relative' }}
        >
            <header className="titlebar-glass h-14 grid grid-cols-[1fr_auto_1fr] items-center px-6 flex-shrink-0">
                <div className="flex items-center gap-3">
                    <span className="h-4 w-4 rounded-full bg-[#ff5f57]" />
                    <span className="h-4 w-4 rounded-full bg-[#ffbd2e]" />
                    <span className="h-4 w-4 rounded-full bg-[#28c840]" />
                </div>
                <div className="text-[20px] font-semibold tracking-normal text-white/75">
                    Obsidian.Brain
                </div>
                <div />
            </header>

            <div className="flex min-h-0 flex-1">
                <ChatSidebar
                    onVaultInfo={() => setIsVaultModalOpen(true)}
                    onSettings={() => setIsSettingsModalOpen(true)}
                    onPrompt={() => setIsPromptModalOpen(true)}
                    systemPromptActive={!!systemPrompt}
                />

                <div className="flex-1 flex flex-col h-full relative min-w-0" style={{ zIndex: 1 }}>

                {/* Chat Area */}
                <div className="flex-1 overflow-y-auto scroll-smooth">
                    {messages.length === 0 ? (
                        /* ── Hero ─────────────────────────────────────── */
                        <div className="flex items-center justify-center min-h-full py-12">
                            <div className="flex w-full max-w-[960px] flex-col items-center gap-8 px-12 py-10" style={{ zIndex: 1 }}>
                                {/* 1. Status pills */}
                                <div className="flex items-center justify-center gap-3 flex-wrap">
                                    <div className="status-pill">
                                        <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#22c55e', boxShadow: '0 0 8px #22c55e', flexShrink: 0, display: 'inline-block' }} />
                                        V: {services.vectorDB.chunks.toLocaleString()} chunks
                                    </div>
                                    <div className="status-pill">
                                        <span style={{ width: 10, height: 10, borderRadius: '50%', background: services.knowledgeGraph.status === 'online' ? '#22c55e' : '#f87171', boxShadow: `0 0 8px ${services.knowledgeGraph.status === 'online' ? '#22c55e' : '#f87171'}`, flexShrink: 0, display: 'inline-block' }} />
                                        G: {services.knowledgeGraph.status === 'online' ? 'Online' : 'Offline'}
                                    </div>
                                    <div className="status-pill">
                                        <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#22c55e', boxShadow: '0 0 8px #22c55e', flexShrink: 0, display: 'inline-block' }} />
                                        L: {lightragNodeLabel} nodes
                                    </div>
                                </div>

                                {/* 2. H1 */}
                                <h1 className="text-center text-[52px] font-bold leading-none text-white" style={{ margin: 0, textShadow: 'none' }}>
                                    Welcome back, Michel
                                </h1>

                                {/* 3. Subtitle */}
                                <p style={{ fontSize: '25px', fontWeight: 400, color: 'rgba(255,255,255,0.60)', margin: 0, textAlign: 'center' }}>
                                    Your Obsidian Brain is online and ready.
                                </p>

                                {/* 4. Spotlight */}
                                <div style={{ width: '100%', maxWidth: '960px', boxShadow: '0 0 60px rgba(176,38,255,0.25), 0 8px 32px rgba(0,0,0,0.4)', borderRadius: '24px' }}>
                                    <div style={{ padding: '1px', background: 'linear-gradient(135deg, rgba(255,214,10,0.55) 0%, rgba(176,38,255,0.40) 50%, rgba(0,209,193,0.40) 100%)', borderRadius: '16px' }}>
                                        <div style={{ background: 'rgba(11,13,18,0.92)', borderRadius: '15px', minHeight: '84px', display: 'flex', alignItems: 'center', paddingLeft: '24px', paddingRight: '10px', gap: '16px' }}>
                                            <Search size={29} className="text-white/55" strokeWidth={2} />
                                            <input
                                                autoFocus
                                                type="text"
                                                value={input}
                                                onChange={(e) => setInput(e.target.value)}
                                                onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                                                placeholder="Ask anything about your vault..."
                                                style={{ flex: 1, background: 'transparent', border: 'none', color: 'white', fontSize: '24px', outline: 'none', caretColor: '#FFD60A', minWidth: 0 }}
                                                className="placeholder-white/30"
                                            />
                                            <button
                                                onClick={handleSendMessage}
                                                disabled={isLoading || !input.trim()}
                                                style={{ background: '#FFD60A', color: '#1a1500', height: '48px', padding: '0 24px', borderRadius: '17px', fontSize: '19px', fontWeight: 700, border: 'none', cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0, opacity: (isLoading || !input.trim()) ? 0.5 : 1 }}
                                            >
                                                Ask
                                            </button>
                                        </div>
                                    </div>
                                </div>

                                {/* 5. Mode segmented control */}
                                <div className="mode-track">
                                    {(['ask', 'research', 'investigate'] as SearchMode[]).map((mode) => (
                                        <button
                                            key={mode}
                                            onClick={() => setSearchMode(mode)}
                                            className={`mode-pill${searchMode === mode ? ' active' : ''}`}
                                        >
                                            {SEARCH_MODE_LABELS[mode]}
                                        </button>
                                    ))}
                                </div>

                                <div className="flex w-full max-w-[960px] flex-col gap-3">
                                    <div className="flex items-center justify-between px-1">
                                        <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-white/30">
                                            Vault suggestions
                                        </span>
                                        <button
                                            onClick={() => setSuggestedPrompts((current) => rotateSuggestedPrompts(current))}
                                            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1.5 text-[11px] font-medium text-white/55 transition-colors hover:border-white/20 hover:bg-white/[0.06] hover:text-white/75"
                                            title="Refresh suggested queries"
                                        >
                                            <RefreshCw size={12} />
                                            Refresh
                                        </button>
                                    </div>
                                    {suggestedPrompts.map((prompt) => (
                                        <button
                                            key={prompt}
                                            onClick={() => setInput(prompt)}
                                            className="suggestion-row"
                                        >
                                            <Sparkles size={21} strokeWidth={1.8} className="text-white/80" />
                                            <span>{prompt}</span>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>
                    ) : (
                        /* ── Chat messages ────────────────────────────── */
                        <div className="p-6">
                            <div className="max-w-3xl mx-auto space-y-6">
                                {graphData && (
                                    <div className="mb-6">
                                        <div className="flex items-center justify-between mb-2">
                                            <div className="text-xs text-white/50">Graph preview</div>
                                            <button
                                                onClick={() => setShowGraph(!showGraph)}
                                                className="text-xs text-white/60 hover:text-white underline underline-offset-2"
                                            >
                                                {showGraph ? 'Hide Graph' : 'Show Graph'}
                                            </button>
                                        </div>
                                        {showGraph ? (
                                            <ForceGraph
                                                data={graphData}
                                                width={700}
                                                height={350}
                                                onNodeClick={(node) => setInput(node.name)}
                                            />
                                        ) : (
                                            <div className="text-xs text-white/40 border border-white/10 rounded-xl p-4 bg-black/30">
                                                Graph rendering is off to reduce CPU/GPU usage. Click "Show Graph" to render.
                                            </div>
                                        )}
                                    </div>
                                )}

                                {messages.map((msg, i) => (
                                    <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                        <div
                                            className={`max-w-[85%] rounded-2xl p-4 ${msg.role === 'user'
                                                ? 'bg-[#FFD60A] text-black shadow-lg shadow-yellow-500/10 rounded-br-none font-medium'
                                                : 'bg-[#1C1C1E] border border-[#2C2C2E] text-white/90 rounded-bl-none shadow-md'
                                                }`}
                                        >
                                            <div className={`prose max-w-none ${msg.role === 'assistant' ? 'prose-invert' : 'prose-neutral'}`}>
                                                <ReactMarkdown
                                                    remarkPlugins={[remarkGfm]}
                                                    components={{
                                                        h1: ({ node, ...props }) => <h1 className="text-2xl font-bold mb-4 mt-6 first:mt-0" {...props} />,
                                                        h2: ({ node, ...props }) => <h2 className="text-xl font-bold mb-3 mt-5 first:mt-0" {...props} />,
                                                        h3: ({ node, ...props }) => <h3 className="text-lg font-semibold mb-2 mt-4 first:mt-0" {...props} />,
                                                        p: ({ node, ...props }) => <p className="mb-3 leading-relaxed" {...props} />,
                                                        ul: ({ node, ...props }) => <ul className="list-disc list-inside mb-3 space-y-1" {...props} />,
                                                        ol: ({ node, ...props }) => <ol className="list-decimal list-inside mb-3 space-y-1" {...props} />,
                                                        li: ({ node, ...props }) => <li className="leading-relaxed" {...props} />,
                                                        a: ({ node, ...props }) => <a className="text-purple-400 hover:text-purple-300 underline" {...props} />,
                                                        code: ({ node, inline, ...props }: any) =>
                                                            inline
                                                                ? <code className="bg-black/30 px-1.5 py-0.5 rounded text-sm font-mono" {...props} />
                                                                : <code className="block bg-black/30 p-3 rounded-lg text-sm font-mono overflow-x-auto mb-3" {...props} />,
                                                        strong: ({ node, ...props }) => <strong className="font-bold" {...props} />,
                                                        em: ({ node, ...props }) => <em className="italic" {...props} />,
                                                    }}
                                                >
                                                    {typeof msg.content === 'string' ? msg.content : String(msg.content || '')}
                                                </ReactMarkdown>
                                            </div>

                                            {msg.role === 'assistant' && msg.sources && (
                                                <SourcesDisplay sources={msg.sources} retrievalIntent={msg.retrievalIntent} />
                                            )}

                                            {msg.role === 'assistant' && msg.enhancedSearch && (
                                                <div className="mt-4 pt-4 border-t border-[#2C2C2E] space-y-3 text-sm">
                                                    {msg.enhancedSearch.llmKnowledge && (
                                                        <div>
                                                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-white/45 mb-2">LLM Knowledge</div>
                                                            <div className="text-white/70 leading-relaxed">{msg.enhancedSearch.llmKnowledge}</div>
                                                        </div>
                                                    )}
                                                    {msg.enhancedSearch.webStatus && (!msg.enhancedSearch.webResults || msg.enhancedSearch.webResults.length === 0) && (
                                                        <div>
                                                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-white/45 mb-2">Web Search</div>
                                                            {msg.enhancedSearch.webSearchTerms && (
                                                                <div className="text-xs text-white/40 mb-1">Terms: {msg.enhancedSearch.webSearchTerms}</div>
                                                            )}
                                                            <div className="text-white/55 italic">{msg.enhancedSearch.webStatus}</div>
                                                        </div>
                                                    )}
                                                </div>
                                            )}

                                            {msg.role === 'assistant' && msg.queryId && (
                                                <RatingButtons
                                                    queryId={msg.queryId}
                                                    query={messages[i - 1]?.content || ''}
                                                    searchMode={searchMode}
                                                    model={settings.model}
                                                    initialRating={msg.rating}
                                                    onRated={(rating) => { msg.rating = rating; }}
                                                />
                                            )}
                                        </div>
                                    </div>
                                ))}

                                {isLoading && (
                                    <div className="flex justify-start">
                                        <ThinkingIndicator message={thinkingLog} />
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>

                {/* Input bar — chat mode only */}
                {messages.length > 0 && (
                    <div className="p-6 bg-gradient-to-t from-black via-black/95 to-transparent flex-shrink-0">
                        <div className="max-w-3xl mx-auto">
                            <div style={{ boxShadow: '0 0 60px rgba(176,38,255,0.25), 0 8px 32px rgba(0,0,0,0.4)', borderRadius: '16px' }}>
                                <div style={{ padding: '1px', background: 'linear-gradient(135deg, rgba(255,214,10,0.55) 0%, rgba(176,38,255,0.40) 50%, rgba(0,209,193,0.40) 100%)', borderRadius: '16px' }}>
                                    <div style={{ background: 'rgba(11,13,18,0.92)', borderRadius: '15px', height: '56px', display: 'flex', alignItems: 'center', paddingLeft: '16px', paddingRight: '8px', gap: '8px' }}>
                                        <input
                                            type="text"
                                            value={input}
                                            autoFocus
                                            onChange={(e) => setInput(e.target.value)}
                                            onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                                            placeholder={`Ask about your vault (${modeLabel} mode)...`}
                                            style={{ flex: 1, background: 'transparent', border: 'none', color: 'white', fontSize: '15px', outline: 'none', caretColor: '#FFD60A' }}
                                            className="placeholder-white/30"
                                        />
                                        <button
                                            onClick={handleSendMessage}
                                            disabled={isLoading || !input.trim()}
                                            style={{ background: '#FFD60A', color: '#1a1500', height: '40px', padding: '0 22px', borderRadius: '14px', fontSize: '14px', fontWeight: 600, border: 'none', cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0, opacity: (isLoading || !input.trim()) ? 0.5 : 1 }}
                                        >
                                            Ask
                                        </button>
                                    </div>
                                </div>
                            </div>
                            <div className="text-center mt-2">
                                <span className="text-[10px] text-white/20 font-medium tracking-wide uppercase">
                                    {modeLabel} mode · {settings.model}
                                </span>
                            </div>
                        </div>
                    </div>
                )}
            </div>
            </div>

            <PromptModal
                isOpen={isPromptModalOpen}
                onClose={() => setIsPromptModalOpen(false)}
                currentPrompt={systemPrompt}
                onSave={(newPrompt) => {
                    setSystemPrompt(newPrompt);
                    setIsPromptModalOpen(false);
                }}
            />

            <VaultInfoModal
                isOpen={isVaultModalOpen}
                onClose={() => setIsVaultModalOpen(false)}
            />

            {isSettingsModalOpen && (
                <SettingsPanelModal onClose={() => setIsSettingsModalOpen(false)} />
            )}
        </div>
    );
}
