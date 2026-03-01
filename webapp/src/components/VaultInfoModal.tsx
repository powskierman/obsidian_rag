import { useApp } from '../context/AppContext';
import { getServiceTone } from '../lib/serviceStatus';

interface VaultInfoModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export default function VaultInfoModal({ isOpen, onClose }: VaultInfoModalProps) {
    const { services } = useApp();
    const vectorTone = getServiceTone(services.vectorDB.status);
    const lightragTone = getServiceTone(services.lightrag?.status || 'offline');
    const knowledgeGraphTone = getServiceTone(services.knowledgeGraph.status);

    if (!isOpen) return null;

    return (
        <div
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
            onClick={onClose}
        >
            <div
                className="bg-[#1C1C1E] rounded-2xl border border-[#2C2C2E] p-6 w-[500px] max-w-[90vw] max-h-[85vh] flex flex-col"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-center justify-between mb-4 flex-shrink-0">
                    <h2 className="text-lg font-semibold text-white">Vault Information</h2>
                    <button
                        onClick={onClose}
                        className="text-white/40 hover:text-white/60 transition-colors"
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <div className="space-y-4 overflow-y-auto pr-2 -mr-2">
                    {/* Vault Details */}
                    <div className="bg-[#2C2C2E] rounded-xl p-4 border border-[#3C3C3E]">
                        <div className="flex items-center gap-2 mb-3">
                            <span className="text-xl">📚</span>
                            <h3 className="text-sm font-semibold text-white">Vault Details</h3>
                        </div>
                        <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                                <span className="text-white/60">Name:</span>
                                <span className="text-white font-medium">Michel</span>
                            </div>
                            <div className="flex justify-between flex-col gap-1">
                                <span className="text-white/60">Location:</span>
                                <span className="text-white/80 font-mono text-[10px] break-all">
                                    /Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Vector Database Stats */}
                    <div className="bg-[#2C2C2E] rounded-xl p-4 border border-[#3C3C3E]">
                        <div className="flex items-center gap-2 mb-3">
                            <span className="text-xl">🔮</span>
                            <h3 className="text-sm font-semibold text-white">Vector Database (ChromaDB)</h3>
                        </div>
                        <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                                <span className="text-white/60">Document Chunks:</span>
                                <span className="text-[#0A84FF] font-semibold">{services.vectorDB.chunks.toLocaleString()}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-white/60">Status:</span>
                                <span className={`${vectorTone.textClass} font-medium`}>
                                    {`● ${vectorTone.label}`}
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* LightRAG Stats */}
                    <div className="bg-[#2C2C2E] rounded-xl p-4 border border-[#3C3C3E]">
                        <div className="flex items-center gap-2 mb-3">
                            <span className="text-xl">⚡</span>
                            <h3 className="text-sm font-semibold text-white">LightRAG (Entity Graph)</h3>
                        </div>
                        <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                                <span className="text-white/60">Graph Nodes:</span>
                                <span className="text-purple-400 font-semibold">{services.lightrag?.nodes ? services.lightrag.nodes.toLocaleString() : '~2,000'}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-white/60">Graph Type:</span>
                                <span className="text-white/80">Entity-centric Semantic</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-white/60">Status:</span>
                                <span className={`${lightragTone.textClass} font-medium`}>{`● ${lightragTone.label}`}</span>
                            </div>
                        </div>
                    </div>

                    {/* NetworkX Graph Stats */}
                    <div className="bg-[#2C2C2E] rounded-xl p-4 border border-[#3C3C3E]">
                        <div className="flex items-center gap-2 mb-3">
                            <span className="text-xl">🕸️</span>
                            <h3 className="text-sm font-semibold text-white">NetworkX (Note Graph)</h3>
                        </div>
                        <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                                <span className="text-white/60">Graph Nodes:</span>
                                <span className="text-indigo-400 font-semibold">{services.knowledgeGraph.entities.toLocaleString()}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-white/60">Relationships:</span>
                                <span className="text-indigo-400 font-semibold">{services.knowledgeGraph.relationships.toLocaleString()}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-white/60">Graph Type:</span>
                                <span className="text-white/80">Note-centric Wiki-links</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-white/60">Status:</span>
                                <span className={`${knowledgeGraphTone.textClass} font-medium`}>
                                    {`● ${knowledgeGraphTone.label}`}
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Summary */}
                    <div className="mt-4 p-3 rounded-lg bg-[#2C2C2E]/50 border border-[#3C3C3E]">
                        <div className="text-xs text-white/40">
                            💡 This vault uses three complementary knowledge sources for comprehensive search:
                            vector similarity (ChromaDB), entity graphs (LightRAG), and note relationships (NetworkX).
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
