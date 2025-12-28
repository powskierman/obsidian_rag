import React from 'react';
import ConfigurationPanel from './sidebar/ConfigurationPanel';
import ChatHistory from './sidebar/ChatHistory';

export default function ChatSidebar() {
    return (
        <div className="w-[280px] h-screen bg-[#1C1C1E] border-r border-[#2C2C2E] flex flex-col flex-shrink-0">
            {/* Header */}
            <div className="p-4 border-b border-[#2C2C2E] shrink-0">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 flex items-center justify-center bg-gradient-to-br from-[#0A84FF]/20 to-[#0077ED]/20 rounded-lg border border-[#0A84FF]/30">
                        {/* Diamond Icon SVG */}
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                             <path d="M12 2L2 12L12 22L22 12L12 2Z" fill="#0A84FF" stroke="#0A84FF" strokeWidth="2" strokeLinejoin="round"/>
                        </svg>
                    </div>
                    <div className="flex flex-col">
                        <h1 className="text-white font-bold text-lg leading-tight">Obsidian RAG</h1>
                        <span className="text-white/40 text-[10px] font-medium tracking-wide uppercase">Knowledge Base</span>
                    </div>
                </div>
            </div>

            {/* Configuration Panel - Compact buttons */}
            <div className="border-b border-[#2C2C2E] shrink-0">
                <ConfigurationPanel />
            </div>

            {/* Chat History - Takes remaining space */}
            <div className="flex-1 overflow-hidden flex flex-col py-3">
                <ChatHistory />
            </div>

            {/* Footer User Profile */}
            <div className="p-4 border-t border-[#2C2C2E] shrink-0">
                <button className="w-full flex items-center gap-3 p-2 rounded-xl hover:bg-white/5 transition-colors text-left group">
                    <div className="w-9 h-9 rounded-full bg-gradient-to-br from-purple-500 to-indigo-500 flex items-center justify-center text-white font-bold shadow-lg">
                        M
                    </div>
                    <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-white group-hover:text-white transition-colors">Michel</div>
                        <div className="text-xs text-white/40 group-hover:text-white/60 transition-colors">Online</div>
                    </div>
                    <svg className="w-4 h-4 text-white/20 group-hover:text-white/50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                </button>
            </div>
        </div>
    );
}
