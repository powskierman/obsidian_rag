'use client';

import React, { useState } from 'react';
import ChatSidebar from '../components/ChatSidebar';
import ThinkingIndicator from '../components/ThinkingIndicator';
import PromptModal from '../components/PromptModal';
import SourcesDisplay from '../components/chat/SourcesDisplay';
import RatingButtons from '../components/chat/RatingButtons';
import { api } from '../lib/api';
import { useApp } from '../context/AppContext';
import { Message, Source } from '../lib/types';

export default function Home() {
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
    } = useApp();

    const [input, setInput] = useState('');
    const [isPromptModalOpen, setIsPromptModalOpen] = useState(false);

    const handleSendMessage = async () => {
        if (!input.trim() || isLoading) return;

        const userMsg = input;
        const queryId = Date.now().toString();
        setInput('');

        // Add user message
        addMessage({ role: 'user', content: userMsg });
        setIsLoading(true);

        try {
            let answer = '';
            let sources: Source[] = [];

            // Use empty model for non-Ollama providers to let backend choose defaults
            const modelToUse = llmProvider === 'ollama' ? settings.model : '';

            // Execute based on search mode
            if (searchMode === 'vector') {
                // Vector search + LLM synthesis (backend handles both)
                try {
                    const result = await api.graphQuery(
                        userMsg,
                        'vector',
                        settings.sources,
                        llmProvider,
                        modelToUse,
                        settings.temperature,
                        systemPrompt,
                        settings.enhancedSearch && ['gemini', 'claude'].includes(llmProvider),
                        settings.enhancedSearch
                    );
                    answer = result.answer;
                    sources = result.sources || [];

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
                } catch (error) {
                    console.error('Vector mode error:', error);
                    answer = `Error: Could not complete vector search with LLM synthesis. ${error}`;
                }

            } else if (searchMode === 'knowledge-graph') {
                // Pure graph reasoning
                const result = await api.graphQuery(
                    userMsg,
                    'graph',
                    settings.sources,
                    llmProvider,
                    modelToUse,
                    settings.temperature,
                    systemPrompt,
                    settings.enhancedSearch && ['gemini', 'claude'].includes(llmProvider),
                    settings.enhancedSearch
                );
                answer = result.answer;

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

            } else if (searchMode === 'hybrid') {
                // Hybrid: graph + vector (backend handles both)
                try {
                    const result = await api.graphQuery(
                        userMsg,
                        'hybrid',
                        settings.sources,
                        llmProvider,
                        modelToUse,
                        settings.temperature,
                        systemPrompt,
                        settings.enhancedSearch && ['gemini', 'claude'].includes(llmProvider),
                        settings.enhancedSearch
                    );
                    answer = result.answer;
                    sources = result.sources || [];

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
                } catch (error) {
                    console.error('Hybrid mode error:', error);
                    answer = `Error: Hybrid search failed. ${error}`;
                }
            }

            // Add assistant message with sources
            const assistantMessage: Message = {
                role: 'assistant',
                content: answer,
                sources: settings.showSources ? sources : undefined,
                queryId,
                timestamp: new Date().toISOString(),
            };

            addMessage(assistantMessage);

        } catch (error) {
            console.error('Query error:', error);
            addMessage({
                role: 'assistant',
                content: "Error: Could not retrieve answer. Check backend availability.",
            });
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex h-screen bg-[#000000] text-white font-sans overflow-hidden selection:bg-[#0A84FF] selection:text-white">
            <ChatSidebar />

            <div className="flex-1 flex flex-col h-full relative min-w-0">
                {/* Header */}
                <header className="h-16 border-b border-[#1C1C1E] flex items-center justify-between px-6 bg-[#000000]/80 backdrop-blur-md sticky top-0 z-10">
                    <div className="flex items-center gap-2">
                        <span className="text-xl font-bold tracking-tight">Deep Thinking</span>
                        <span className="px-2 py-0.5 rounded-full bg-[#1C1C1E] border border-[#2C2C2E] text-[10px] font-medium text-white/60 uppercase tracking-wider">Beta</span>
                    </div>

                    <div className="flex items-center gap-1 bg-[#1C1C1E] p-1 rounded-lg border border-[#2C2C2E]">
                        <button className="px-3 py-1.5 rounded-md text-sm font-medium text-white/60 hover:text-white hover:bg-white/5 transition-all">
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
                    </div>
                </header>

                {/* Chat Area */}
                <div className="flex-1 overflow-y-auto p-6 scroll-smooth">
                    <div className="max-w-3xl mx-auto space-y-6">
                        {messages.length === 0 && (
                            <div className="flex flex-col items-center justify-center h-[60vh] text-center space-y-4">
                                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#1C1C1E] to-[#2C2C2E] flex items-center justify-center shadow-2xl border border-white/5">
                                    <span className="text-3xl">🧠</span>
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold text-white mb-2">Ready to think deeply?</h2>
                                    <p className="text-white/40 max-w-md mx-auto">
                                        Ask complex questions about your Obsidian vault using {searchMode} mode with {llmProvider}.
                                    </p>
                                </div>
                            </div>
                        )}

                        {messages.map((msg, i) => (
                            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div
                                    className={`max-w-[85%] rounded-2xl p-4 ${msg.role === 'user'
                                            ? 'bg-[#0A84FF] text-white shadow-lg shadow-blue-500/10 rounded-br-none'
                                            : 'bg-[#1C1C1E] border border-[#2C2C2E] text-white/90 rounded-bl-none shadow-xl'
                                        }`}
                                >
                                    <div className="prose prose-invert prose-sm max-w-none">
                                        {(typeof msg.content === 'string' ? msg.content : String(msg.content || '')).split('\n').map((line, j) => (
                                            <p key={j} className="mb-2 last:mb-0 leading-relaxed opacity-90">{line}</p>
                                        ))}
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
                                <ThinkingIndicator />
                            </div>
                        )}
                    </div>
                </div>

                {/* Input Area */}
                <div className="p-6 bg-gradient-to-t from-black via-black/95 to-transparent">
                    <div className="max-w-3xl mx-auto relative">
                        <input
                            type="text"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                            placeholder={`Ask about your vault (${searchMode} mode)...`}
                            className="w-full bg-[#1C1C1E]/80 backdrop-blur-xl border border-[#2C2C2E] rounded-2xl py-4 px-5 pr-12 text-white placeholder-white/30 focus:outline-none focus:border-[#0A84FF]/50 focus:ring-1 focus:ring-[#0A84FF]/50 transition-all shadow-2xl"
                        />
                        <button
                            onClick={handleSendMessage}
                            disabled={isLoading || !input.trim()}
                            className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-xl bg-[#0A84FF] text-white hover:bg-[#0071E3] disabled:opacity-50 disabled:hover:bg-[#0A84FF] transition-all shadow-lg hover:shadow-blue-500/20"
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
        </div>
    );
}
