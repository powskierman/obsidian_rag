'use client';

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Settings } from 'lucide-react';
import ChatSidebar from '../components/ChatSidebar';
import ThinkingIndicator from '../components/ThinkingIndicator';
import PromptModal from '../components/PromptModal';
import VaultInfoModal from '../components/VaultInfoModal';
import SettingsPanelModal from '../components/sidebar/SettingsPanelModal';
import ForceGraph from '../components/ForceGraph';
import SourcesDisplay from '../components/chat/SourcesDisplay';
import RatingButtons from '../components/chat/RatingButtons';
import StaticHexBackground from '../components/StaticHexBackground';
import { api } from '../lib/api';
import { useApp } from '../context/AppContext';
import { EnhancedSearchData, SearchMode, Source } from '../lib/types';

const SEARCH_MODE_LABELS: Record<SearchMode, string> = {
    vector: 'vector',
    cascading: 'cascading',
    vault_review: 'deep review',
    'deep-thinking': 'deep thinking',
};

const REVIEW_QUERY_SIGNAL_RE = /\b(?:review|analy[sz]e|assess|evaluate)\b/i;
const REVIEW_SCOPE_SIGNAL_RE = /\b(?:my|vault|notes|scans|bloodwork|labs|results)\b/i;
const REVIEW_BROAD_SIGNAL_RE = /\b(?:deep review|comprehensive|all my|entire vault|full vault)\b/i;
const REVIEW_PROTECTED_PHRASE_RE = /\bpet\s*(?:\/|\band\b)?\s*ct\b/i;

const isComprehensiveReviewQuery = (query: string): boolean => {
    const normalized = query.trim();
    if (!normalized || !REVIEW_QUERY_SIGNAL_RE.test(normalized)) {
        return false;
    }
    const protectedText = normalized.replace(REVIEW_PROTECTED_PHRASE_RE, 'pet_ct');
    const commaCount = (protectedText.match(/[,;]/g) || []).length;
    const andCount = (protectedText.match(/\band\b/gi) || []).length;
    return (
        (REVIEW_SCOPE_SIGNAL_RE.test(normalized) && (commaCount > 0 || andCount > 0))
        || REVIEW_BROAD_SIGNAL_RE.test(normalized)
    );
};

const resolveBackendMode = (selectedMode: SearchMode, query: string): SearchMode => {
    if (selectedMode === 'cascading' && isComprehensiveReviewQuery(query)) {
        return 'vault_review';
    }
    return selectedMode;
};

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
    } = useApp();

    console.log('Home component state:', { messages, isLoading, searchMode });

    const [input, setInput] = useState('');
    const [isPromptModalOpen, setIsPromptModalOpen] = useState(false);
    const [isVaultModalOpen, setIsVaultModalOpen] = useState(false);
    const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
    const [thinkingLog, setThinkingLog] = useState<string>('');
    const [graphData, setGraphData] = useState<{ nodes: any[], links: any[] } | null>(null);
    const [showGraph, setShowGraph] = useState(false);
    const modeLabel = SEARCH_MODE_LABELS[searchMode] || searchMode;
    const isDeepThinkingMode = searchMode === 'deep-thinking';
    const deepReviewAvailable = isComprehensiveReviewQuery(input);
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
                // Standard Unified Search (HTTP)
                const backendMode = resolveBackendMode(searchMode, userMsg);

                // Use empty model for non-Ollama providers to let backend choose defaults
                const modelToUse = llmProvider === 'ollama' || llmProvider === 'openrouter' || llmProvider === 'chatgpt' || llmProvider === 'lmstudio' ? settings.model : '';

                // Unified Search Call
                console.log('📡 Sending query settings:', {
                    mode: backendMode,
                    sources: settings.sources,
                    relevanceThreshold: settings.relevanceThreshold
                });
                const result = await api.unifiedSearch(
                    userMsg,
                    backendMode as any,
                    settings.sources,
                    llmProvider,
                    modelToUse,
                    settings.temperature,
                    settings.relevanceThreshold,
                    settings.enhancedSearch,
                    settings.briefConceptIndex,
                    systemPrompt
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

    return (
        <>
            {/* Lightweight Static Hex Background */}
            <StaticHexBackground />

            {/* Main UI - positioned above background */}
            <div className="flex h-screen bg-transparent text-white font-sans overflow-hidden selection:bg-[#FFD60A] selection:text-black relative">
                <ChatSidebar />

                <div className="flex-1 flex flex-col h-full relative min-w-0">
                    {/* Header */}
                    <header className="h-32 border-b border-[#1C1C1E] flex items-center justify-between px-6 bg-[#0B0D12]/90 sticky top-0 z-30">
                        <div className="flex items-center pt-6">
                            <img src="/logo.png" alt="Obsidian RAG" className="w-[150px] h-auto object-contain" />
                        </div>

                        <div className="flex items-center gap-1 bg-[#1C1C1E] p-1 rounded-lg border border-[#2C2C2E]">
                            <button
                                onClick={() => setIsVaultModalOpen(true)}
                                className="px-3 py-1.5 rounded-md text-sm font-medium text-white/60 hover:text-white hover:bg-white/5 transition-all"
                            >
                                Vault
                            </button>
                            <div className="w-[1px] h-4 bg-white/10" />
                            <button
                                onClick={() => setIsPromptModalOpen(true)}
                                className="px-3 py-1.5 rounded-md text-sm font-medium text-white/60 hover:text-white hover:bg-white/5 transition-all flex items-center gap-2"
                            >
                                <span>Prompt</span>
                                {systemPrompt && <div className="w-1.5 h-1.5 rounded-full bg-[#0A84FF]" />}
                            </button>
                            <div className="w-[1px] h-4 bg-white/10" />
                            <button
                                onClick={() => setIsSettingsModalOpen(true)}
                                className="px-2 py-1.5 rounded-md text-white/60 hover:text-white hover:bg-white/5 transition-all"
                                title="Settings"
                            >
                                <Settings size={18} />
                            </button>
                        </div>
                    </header>

                    {/* Chat Area */}
                    <div className="flex-1 overflow-y-auto p-6 scroll-smooth">
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
                                            onNodeClick={(node) => {
                                                setInput(node.name);
                                                // Optional: Auto-search
                                                // handleSendMessage(); 
                                            }}
                                        />
                                    ) : (
                                        <div className="text-xs text-white/40 border border-white/10 rounded-xl p-4 bg-black/30">
                                            Graph rendering is off to reduce CPU/GPU usage. Click "Show Graph" to render.
                                        </div>
                                    )}
                                </div>
                            )}

                            {messages.length === 0 && (
                                <div className="flex items-center justify-center h-[70vh] w-full relative">
                                    <div className="z-10 w-full max-w-2xl space-y-8 px-4">
                                        <div className="text-center space-y-2">
                                            <h1 className="text-4xl font-bold text-white tracking-tight">Welcome back, Michel</h1>
                                            <p className="text-white/40">Your Obsidian Brain is online and ready.</p>
                                        </div>

                                        {/* Spotlight Search Bar */}
                                        <div className="relative">
                                            <div className="rounded-2xl p-[1px] bg-gradient-to-r from-[#FFD60A]/50 via-[#6B8CFF]/35 to-[#00D1C1]/35">
                                                <div className="rounded-[16px] p-[1px] bg-white/10">
                                                    <div className="relative bg-[#0B0D12]/80 border border-white/10 rounded-[15px] flex items-center p-2 shadow-lg">
                                                        <input
                                                            autoFocus
                                                            type="text"
                                                            value={input}
                                                            onChange={(e) => setInput(e.target.value)}
                                                            onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                                                            placeholder={`Search (${modeLabel})...`}
                                                            className="flex-1 bg-transparent border-none text-white placeholder-white/30 px-4 py-2 text-lg focus:ring-0 focus:outline-none"
                                                        />

                                                        {/* Mode Selector */}
                                                        <select
                                                            value={searchMode}
                                                            onChange={(e) => setSearchMode(e.target.value as any)}
                                                            className="bg-accent-gold text-black px-4 py-2 rounded-lg text-xs font-medium shadow-lg shadow-yellow-500/20 border-none focus:ring-2 focus:ring-yellow-500/50 cursor-pointer"
                                                        >
                                                            <option value="vector">Vector (ChromaDB)</option>
                                                            <option value="cascading">Cascading (Waterfall)</option>
                                                            <option value="vault_review">Deep Review (Full Notes)</option>
                                                            <option value="deep-thinking">Deep Thinking (Agentic)</option>
                                                        </select>
                                                    </div>
                                                </div>
                                            </div>

                                            {deepReviewAvailable && searchMode !== 'deep-thinking' && (
                                                <div className="mt-3 flex items-center justify-between rounded-xl border border-[#FFD60A]/25 bg-[#FFD60A]/8 px-4 py-3 text-sm">
                                                    <div className="text-white/75">
                                                        Comprehensive vault review detected. Use full-note Deep Review instead of snippet RAG.
                                                    </div>
                                                    <button
                                                        onClick={() => setSearchMode('vault_review')}
                                                        className={`ml-4 shrink-0 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                                                            searchMode === 'vault_review'
                                                                ? 'bg-[#FFD60A] text-black'
                                                                : 'bg-white/10 text-white hover:bg-white/15'
                                                        }`}
                                                    >
                                                        {searchMode === 'vault_review' ? 'Deep Review On' : 'Deep Review'}
                                                    </button>
                                                </div>
                                            )}
                                        </div>

                                        {/* Status Pills */}
                                        <div className="flex items-center justify-center gap-4">
                                            <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10">
                                                <div className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                                                <span className="text-xs font-mono text-purple-200">V: 7,055 chunks</span>
                                            </div>
                                            <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10">
                                                <div className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
                                                <span className="text-xs font-mono text-indigo-200">G: Online</span>
                                            </div>
                                        </div>
                                    </div>
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

                                        {/* Sources Display */}
                                        {msg.role === 'assistant' && msg.sources && (
                                            <SourcesDisplay
                                                sources={msg.sources}
                                                retrievalIntent={msg.retrievalIntent}
                                            />
                                        )}

                                        {msg.role === 'assistant' && msg.enhancedSearch && (
                                            <div className="mt-4 pt-4 border-t border-[#2C2C2E] space-y-3 text-sm">
                                                {msg.enhancedSearch.llmKnowledge && (
                                                    <div>
                                                        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-white/45 mb-2">
                                                            LLM Knowledge
                                                        </div>
                                                        <div className="text-white/70 leading-relaxed">
                                                            {msg.enhancedSearch.llmKnowledge}
                                                        </div>
                                                    </div>
                                                )}

                                                {msg.enhancedSearch.webStatus && (!msg.enhancedSearch.webResults || msg.enhancedSearch.webResults.length === 0) && (
                                                    <div>
                                                        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-white/45 mb-2">
                                                            Web Search
                                                        </div>
                                                        {msg.enhancedSearch.webSearchTerms && (
                                                            <div className="text-xs text-white/40 mb-1">
                                                                Terms: {msg.enhancedSearch.webSearchTerms}
                                                            </div>
                                                        )}
                                                        <div className="text-white/55 italic">
                                                            {msg.enhancedSearch.webStatus}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        {/* Rating Buttons */}
                                        {msg.role === 'assistant' && msg.queryId && (
                                            <RatingButtons
                                                queryId={msg.queryId}
                                                query={messages[i - 1]?.content || ''}
                                                searchMode={searchMode}
                                                model={settings.model}
                                                initialRating={msg.rating}
                                                onRated={(rating) => {
                                                    // Update message with rating
                                                    msg.rating = rating;
                                                }}
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

                    {/* Input Area (Only show when chatting) */}
                    {messages.length > 0 && (
                        <div className="p-6 bg-gradient-to-t from-black via-black/95 to-transparent">
                            <div className="max-w-3xl mx-auto relative">
                                <div className="rounded-2xl p-[1px] bg-gradient-to-r from-[#FFD60A]/45 via-[#6B8CFF]/30 to-[#00D1C1]/30">
                                    <div className="rounded-[16px] p-[1px] bg-white/10">
                                        <div className="relative">
                                            <input
                                                type="text"
                                                value={input}
                                                autoFocus
                                                onChange={(e) => setInput(e.target.value)}
                                                onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                                                placeholder={`Ask about your vault (${modeLabel} mode)...`}
                                                className="w-full bg-[#121418] border border-[#2C2C2E] rounded-[15px] py-4 px-5 pr-12 text-white placeholder-white/30 focus:outline-none focus:border-[#FFD60A]/50 focus:ring-1 focus:ring-[#FFD60A]/50 transition-colors shadow-lg"
                                            />
                                            <button
                                                onClick={handleSendMessage}
                                                disabled={isLoading || !input.trim()}
                                                className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-xl bg-[#FFD60A] text-black hover:bg-[#FFC600] disabled:opacity-50 disabled:hover:bg-[#FFD60A] transition-colors shadow-lg hover:shadow-yellow-500/20"
                                            >
                                                <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
                                                </svg>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div className="text-center mt-3">
                                <span className="text-[10px] text-white/20 font-medium tracking-wide uppercase">
                                    Mode: {modeLabel} • Model: {settings.model}
                                </span>
                            </div>
                        </div>
                    )}
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
                    <SettingsPanelModal
                        onClose={() => setIsSettingsModalOpen(false)}
                    />
                )}
            </div>
        </>
    );
}
