import React, { useState, useEffect } from 'react';

interface PromptModalProps {
    isOpen: boolean;
    onClose: () => void;
    currentPrompt: string;
    onSave: (prompt: string) => void;
}

const DEFAULT_PROMPT = `You are a Deep Thinking AI assistant for an Obsidian Knowledge Base.
Your goal is to answer questions by analyzing the provided Vault Context and using Graph Reasoning.

Context:
{context}

Question:
{question}`;

export default function PromptModal({ isOpen, onClose, currentPrompt, onSave }: PromptModalProps) {
    const [prompt, setPrompt] = useState(currentPrompt || DEFAULT_PROMPT);

    useEffect(() => {
        if (isOpen) {
            setPrompt(currentPrompt || DEFAULT_PROMPT);
        }
    }, [isOpen, currentPrompt]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
            <div className="bg-[#1C1C1E] rounded-2xl border border-[#2C2C2E] w-full max-w-2xl shadow-lg overflow-hidden animate-in fade-in zoom-in duration-200">
                <div className="p-4 border-b border-[#2C2C2E] flex items-center justify-between bg-[#2C2C2E]/30">
                    <h3 className="font-semibold text-white">Configure Search Prompt</h3>
                    <button onClick={onClose} className="text-white/50 hover:text-white transition-colors">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M18 6L6 18M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <div className="p-6 space-y-4">
                    <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 text-sm text-blue-200">
                        <p className="font-medium mb-1">Tips:</p>
                        <ul className="list-disc list-inside space-y-1 opacity-80">
                            <li>Use <code>{'{'}context{'}'}</code> for retrieved notes/graph data</li>
                            <li>Use <code>{'{'}question{'}'}</code> for the user&apos;s query</li>
                        </ul>
                    </div>

                    <textarea
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                        className="w-full h-[300px] bg-[#000000]/50 border border-[#2C2C2E] rounded-xl p-4 text-sm font-mono text-white/90 focus:outline-none focus:border-[#0A84FF] focus:ring-1 focus:ring-[#0A84FF] resize-none"
                        placeholder="Enter system prompt..."
                    />
                </div>

                <div className="p-4 border-t border-[#2C2C2E] bg-[#2C2C2E]/30 flex justify-between items-center">
                    <button
                        onClick={() => setPrompt(DEFAULT_PROMPT)}
                        className="px-4 py-2 rounded-lg text-white/50 hover:text-white hover:bg-white/5 text-sm font-medium transition-colors"
                    >
                        Reset to Default
                    </button>
                    <div className="flex gap-2">
                         <button
                            onClick={onClose}
                            className="px-4 py-2 rounded-lg hover:bg-white/5 text-white text-sm font-medium transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={() => onSave(prompt)}
                            className="px-4 py-2 rounded-lg bg-[#0A84FF] hover:bg-[#0077ED] text-white text-sm font-medium transition-colors shadow-lg shadow-blue-500/10"
                        >
                            Save Changes
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
