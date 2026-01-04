'use client';

import React, { useState } from 'react';
import dynamic from 'next/dynamic';
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
import { ErrorBoundary } from '../components/ErrorBoundary';
import FallbackBackground from '../components/FallbackBackground';
import { api } from '../lib/api';
import { useApp } from '../context/AppContext';
import { Message, Source } from '../lib/types';

// Dynamically import simplified knowledge graph - NO SSR
const KnowledgeGraph3D = dynamic(() => import('../components/KnowledgeGraphSimple'), {
    ssr: false,
});

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
    const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

    React.useEffect(() => {
        setDimensions({ width: window.innerWidth, height: window.innerHeight });
        const handleResize = () => setDimensions({ width: window.innerWidth, height: window.innerHeight });
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    const handleSendMessage = async () => {
        if (!input.trim() || isLoading) return;

        const userMsg = input;
        const queryId = Date.now().toString();
        setInput('');
        setThinkingLog('');

        // Add user message
        addMessage({ role: 'user', content: userMsg });
        setIsLoading(true);

        try {
            // Deep Thinking Mode (WebSocket)
            if (settings.deepThinking) {
                const ws = new WebSocket(api.deepResearchEndpoint);

                ws.onopen = () => {
                    // Send query AND selected provider
                    ws.send(JSON.stringify({
                        query: userMsg,
                        provider: llmProvider
                    }));
                };

                ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);

                        if (data.type === 'log' || data.type === 'status') {
                            setThinkingLog(data.content || data.message);
                        } else if (data.type === 'result') {
                            // Final result received
                            const answer = data.data?.answer || data.markdown || data.content;
                            if (answer) {
                                // Extract and map citations to structured Source objects
                                const rawCitations = data.data?.citations || [];
                                // Flatten if the model returned nested lists accidentally
                                const flatCitations = Array.isArray(rawCitations) ? rawCitations.flat() : [rawCitations];

                                const mappedSources: Source[] = flatCitations.map((cit: any) => {
                                    const citStr = typeof cit === 'string' ? cit : JSON.stringify(cit);

                                    // Handle Obsidian link format [[Path/To/File]]
                                    if (citStr.includes('[[') && citStr.includes(']]')) {
                                        const match = citStr.match(/\[\[(.*?)\]\]/);
                                        const inner = match ? match[1] : citStr;
                                        return {
                                            filename: inner.split('/').pop() || inner,
                                            filepath: inner,
                                            relevance: 95,
                                            snippet: 'Cited via Research Reasoning'
                                        };
                                    }

                                    // Handle standard markdown-ish links [Note Name]
                                    if (citStr.startsWith('[') && citStr.endsWith(']')) {
                                        const inner = citStr.substring(1, citStr.length - 1);
                                        return {
                                            filename: inner.split('/').pop() || inner,
                                            filepath: inner,
                                            relevance: 90,
                                            snippet: 'Identified during analysis'
                                        };
                                    }

                                    // Handle URLs
                                    if (citStr.startsWith('http')) {
                                        return {
                                            filename: 'Web Source',
                                            filepath: citStr,
                                            relevance: 85,
                                            snippet: citStr
                                        };
                                    }

                                    // Fallback for other formats
                                    return {
                                        filename: citStr,
                                        filepath: citStr,
                                        relevance: 80,
                                        snippet: 'Retrieved during research'
                                    };
                                });

                                addMessage({
                                    role: 'assistant',
                                    content: answer,
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
                            console.error('Deep Thinking Error:', data.content);
                            addMessage({
                                role: 'assistant',
                                content: `Error: ${data.content}`,
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
                const backendMode = searchMode;

                // Use empty model for non-Ollama providers to let backend choose defaults
                const modelToUse = llmProvider === 'ollama' ? settings.model : '';

                // Unified Search Call
                const result = await api.unifiedSearch(
                    userMsg,
                    backendMode as any,
                    settings.sources,
                    llmProvider,
                    modelToUse,
                    settings.temperature,
                    settings.enhancedSearch,
                    systemPrompt
                );

                let answer = result.answer;
                const sources: Source[] = result.sources || [];

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

                // Append enhanced search content if available
                if (settings.enhancedSearch) {
                    if (result.llm_knowledge) {
                        const kbText = typeof result.llm_knowledge === 'string'
                            ? result.llm_knowledge
                            : JSON.stringify(result.llm_knowledge);
                        answer += `\n\n---\n\n### 🧠 LLM Knowledge\n\n${kbText}`;
                    }

                    if (result.web_search && result.web_search.results) {
                        const webResults = result.web_search.results
                            .map((r: any, i: number) => `${i + 1}. [${r.title}](${r.url})\n   ${r.content.substring(0, 200)}...`)
                            .join('\n\n');
                        const searchTerms = result.web_search.search_terms || '';
                        answer += `\n\n---\n\n### 🌐 Web Search\n\n**Terms**: _${searchTerms}_\n\n${webResults}`;
                    }
                }

                addMessage({
                    role: 'assistant',
                    content: answer,
                    sources: settings.showSources ? sources : undefined,
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
            {/* 3D Knowledge Graph Background - Outside main container */}
            <div className="fixed inset-0 pointer-events-none">
                <ErrorBoundary fallback={<FallbackBackground />}>
                    <KnowledgeGraph3D />
                </ErrorBoundary>
            </div>

            {/* Main UI - positioned above background */}
            <div className="flex h-screen bg-transparent text-white font-sans overflow-hidden selection:bg-[#FFD60A] selection:text-black relative">
                <ChatSidebar />

                <div className="flex-1 flex flex-col h-full relative min-w-0">
                    {/* Header */}
                    <header className="h-32 border-b border-[#1C1C1E] flex items-center justify-between px-6 bg-[#000000]/60 backdrop-blur-xl sticky top-0 z-30">
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
                                        <div className="relative group">
                                            <div className="absolute -inset-0.5 bg-gradient-to-r from-purple-500 to-indigo-500 rounded-2xl opacity-30 blur group-hover:opacity-50 transition duration-500" />
                                            <div className="relative bg-[#000000]/40 backdrop-blur-2xl border border-white/10 rounded-2xl flex items-center p-2 shadow-2xl">
                                                <input
                                                    autoFocus
                                                    type="text"
                                                    value={input}
                                                    onChange={(e) => setInput(e.target.value)}
                                                    onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                                                    placeholder={`Search (${searchMode})...`}
                                                    className="flex-1 bg-transparent border-none text-white placeholder-white/30 px-4 py-2 text-lg focus:ring-0 focus:outline-none"
                                                />

                                                {/* Mode Selector */}
                                                <select
                                                    value={searchMode}
                                                    onChange={(e) => setSearchMode(e.target.value as any)}
                                                    className="bg-accent-gold text-black px-4 py-2 rounded-lg text-xs font-medium shadow-lg shadow-yellow-500/20 border-none focus:ring-2 focus:ring-yellow-500/50 cursor-pointer"
                                                >
                                                    <optgroup label="🎯 Single Source">
                                                        <option value="vector">Vector (ChromaDB)</option>
                                                        <option value="notes">Notes (NetworkX)</option>
                                                        <option value="entities">Entities (LightRAG)</option>
                                                    </optgroup>
                                                    <optgroup label="🔗 Dual Source">
                                                        <option value="notes+vector">Notes + Vector</option>
                                                        <option value="entities+vector">Entities + Vector</option>
                                                        <option value="dual-graph">Dual Graph</option>
                                                    </optgroup>
                                                    <optgroup label="⚡ Ultimate">
                                                        <option value="hybrid">Hybrid (All 3)</option>
                                                        <option value="cascading">Cascading (Waterfall)</option>
                                                    </optgroup>
                                                </select>
                                            </div>
                                        </div>

                                        {/* Status Pills */}
                                        <div className="flex items-center justify-center gap-4">
                                            <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 backdrop-blur-md">
                                                <div className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse" />
                                                <span className="text-xs font-mono text-purple-200">V: 7,055 chunks</span>
                                            </div>
                                            <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 backdrop-blur-md">
                                                <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />
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
                                            : 'bg-[#1C1C1E] border border-[#2C2C2E] text-white/90 rounded-bl-none shadow-xl'
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
                                            <SourcesDisplay sources={msg.sources} />
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
                                <input
                                    type="text"
                                    value={input}
                                    autoFocus
                                    onChange={(e) => setInput(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                                    placeholder={`Ask about your vault (${searchMode} mode)...`}
                                    className="w-full bg-[#1C1C1E]/80 backdrop-blur-xl border border-[#2C2C2E] rounded-2xl py-4 px-5 pr-12 text-white placeholder-white/30 focus:outline-none focus:border-[#FFD60A]/50 focus:ring-1 focus:ring-[#FFD60A]/50 transition-all shadow-2xl"
                                />
                                <button
                                    onClick={handleSendMessage}
                                    disabled={isLoading || !input.trim()}
                                    className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-xl bg-[#FFD60A] text-black hover:bg-[#FFC600] disabled:opacity-50 disabled:hover:bg-[#FFD60A] transition-all shadow-lg hover:shadow-yellow-500/20"
                                >
                                    <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
                                    </svg>
                                </button>
                            </div>
                            <div className="text-center mt-3">
                                <span className="text-[10px] text-white/20 font-medium tracking-wide uppercase">
                                    Mode: {searchMode} • Model: {settings.model}
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
