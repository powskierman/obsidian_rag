import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { getKnowledgeGraphServiceState, getServiceTone, getVectorServiceState } from '../lib/serviceStatus';

interface SettingsModalProps {
    isOpen: boolean;
    onClose: () => void;
    currentModel: string;
    onModelChange: (model: string) => void;
}

export default function SettingsModal({ isOpen, onClose, currentModel, onModelChange }: SettingsModalProps) {
    const [stats, setStats] = useState<{ documents: number; graph: any } | null>(null);
    const [isLoadingStats, setIsLoadingStats] = useState(false);

    // Legacy Controls State
    const [searchMode, setSearchMode] = useState<'vector' | 'cascading' | 'deep-thinking'>('cascading');
    const [llmProvider, setLlmProvider] = useState<'ollama' | 'gemini' | 'claude' | 'chatgpt'>('gemini');

    useEffect(() => {
        if (isOpen) {
            checkStats();
        }
    }, [isOpen]);

    const checkStats = async () => {
        setIsLoadingStats(true);
        const data = await api.getStats();
        setStats(data);
        setIsLoadingStats(false);
    };

    if (!isOpen) return null;

    const vectorTone = getServiceTone(getVectorServiceState(stats?.documents ?? 0));
    const graphTone = getServiceTone(getKnowledgeGraphServiceState(stats?.graph ?? null));

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70">
            <div className="bg-[#1C1C1E] rounded-2xl border border-[#2C2C2E] w-full max-w-md shadow-lg overflow-hidden animate-in fade-in zoom-in duration-200 h-[80vh] flex flex-col">
                <div className="p-4 border-b border-[#2C2C2E] flex items-center justify-between bg-[#2C2C2E]/30 shrink-0">
                    <h3 className="font-semibold text-white">Settings</h3>
                    <button onClick={onClose} className="text-white/50 hover:text-white transition-colors">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M18 6L6 18M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <div className="p-6 space-y-6 overflow-y-auto flex-1">

                    {/* Search Mode */}
                    <div className="space-y-3">
                        <label className="text-xs font-semibold text-white/40 uppercase tracking-wider flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                            Search Mode
                        </label>
                        <div className="grid grid-cols-1 gap-2">
                             {(['vector', 'cascading', 'deep-thinking'] as const).map(mode => (
                                <label key={mode} className={`flex items-center p-3 rounded-xl border cursor-pointer transition-all ${searchMode === mode ? 'bg-[#0A84FF]/10 border-[#0A84FF]' : 'bg-[#1C1C1E] border-[#2C2C2E] hover:border-white/20'}`}>
                                    <input type="radio" name="searchMode" checked={searchMode === mode} onChange={() => setSearchMode(mode)} className="hidden"/>
                                    <div className="flex-1">
                                        <div className="text-sm font-medium text-white capitalize">{mode}</div>
                                        <div className="text-xs text-white/50">{mode === 'vector' ? 'Fast retrieval' : mode === 'cascading' ? 'Multi-stage retrieval' : 'Agentic reasoning'}</div>
                                    </div>
                                    <div className={`w-4 h-4 rounded-full border flex items-center justify-center ${searchMode === mode ? 'border-[#0A84FF]' : 'border-white/20'}`}>
                                        {searchMode === mode && <div className="w-2 h-2 rounded-full bg-[#0A84FF]" />}
                                    </div>
                                </label>
                             ))}
                        </div>
                    </div>

                    {/* LLM Provider */}
                    <div className="space-y-3">
                        <label className="text-xs font-semibold text-white/40 uppercase tracking-wider flex items-center gap-2">
                            <span className="text-lg">🤖</span> LLM Provider
                        </label>
                        <div className="grid gap-2">
                           <button onClick={() => setLlmProvider('ollama')} className={`flex items-center justify-between p-3 rounded-xl border transition-all ${llmProvider === 'ollama' ? 'bg-[#0A84FF]/10 border-[#0A84FF] text-white' : 'bg-[#1C1C1E] border-[#2C2C2E] text-white/60'}`}>
                                <div className="text-sm font-medium">Ollama (Free)</div>
                                {llmProvider === 'ollama' && <div className="w-2 h-2 rounded-full bg-[#0A84FF]" />}
                           </button>
                           <button onClick={() => setLlmProvider('gemini')} className={`flex items-center justify-between p-3 rounded-xl border transition-all ${llmProvider === 'gemini' ? 'bg-[#0A84FF]/10 border-[#0A84FF] text-white' : 'bg-[#1C1C1E] border-[#2C2C2E] text-white/60'}`}>
                                <div className="text-sm font-medium">Gemini Pro ($)</div>
                                {llmProvider === 'gemini' && <div className="w-2 h-2 rounded-full bg-[#0A84FF]" />}
                           </button>
                           <button onClick={() => setLlmProvider('claude')} className={`flex items-center justify-between p-3 rounded-xl border transition-all ${llmProvider === 'claude' ? 'bg-[#0A84FF]/10 border-[#0A84FF] text-white' : 'bg-[#1C1C1E] border-[#2C2C2E] text-white/60'}`}>
                                <div className="text-sm font-medium">Claude API ($)</div>
                                {llmProvider === 'claude' && <div className="w-2 h-2 rounded-full bg-[#0A84FF]" />}
                           </button>
                           <button onClick={() => setLlmProvider('chatgpt')} className={`flex items-center justify-between p-3 rounded-xl border transition-all ${llmProvider === 'chatgpt' ? 'bg-[#0A84FF]/10 border-[#0A84FF] text-white' : 'bg-[#1C1C1E] border-[#2C2C2E] text-white/60'}`}>
                                <div className="text-sm font-medium">ChatGPT (OpenAI) ($)</div>
                                {llmProvider === 'chatgpt' && <div className="w-2 h-2 rounded-full bg-[#0A84FF]" />}
                           </button>
                        </div>
                    </div>

                    {/* Detailed System Status */}
                    <div className="space-y-3">
                        <div className="flex items-center justify-between">
                            <label className="text-xs font-semibold text-white/40 uppercase tracking-wider">Services Status</label>
                            <button onClick={checkStats} className="text-[10px] text-[#0A84FF] hover:underline">Refresh</button>
                        </div>

                        <div className="bg-black/20 rounded-xl p-4 space-y-3 border border-[#2C2C2E]">
                            <div className="flex items-center justify-between text-sm">
                                <span className="text-white/60 flex items-center gap-2">
                                    <div className={`w-1.5 h-1.5 rounded-full ${vectorTone.dotClass}`}></div>
                                    Vector DB Chunks
                                </span>
                                <span className={`font-mono font-medium ${vectorTone.textClass}`}>{stats?.documents ?? '0'} chunks</span>
                            </div>

                            <div className="flex items-center justify-between text-sm">
                                <span className="text-white/60 flex items-center gap-2">
                                    <div className={`w-1.5 h-1.5 rounded-full ${graphTone.dotClass}`}></div>
                                    Graph Entities
                                </span>
                                <span className={`font-mono font-medium ${graphTone.textClass}`}>{graphTone.label}</span>
                            </div>

                             <div className="flex items-center justify-between text-sm">
                                <span className="text-white/60 flex items-center gap-2">
                                    <div className="w-1.5 h-1.5 rounded-full bg-green-500"></div>
                                    Ollama Models
                                </span>
                                <span className="text-white font-mono font-medium">2 available</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="p-4 border-t border-[#2C2C2E] bg-[#2C2C2E]/30 flex justify-end shrink-0">
                    <button onClick={onClose} className="px-4 py-2 rounded-lg bg-[#0A84FF] hover:bg-[#0077ED] text-white text-sm font-medium transition-colors shadow-lg shadow-blue-500/10">
                        Done
                    </button>
                </div>
            </div>
        </div>
    );
}
