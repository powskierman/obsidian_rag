import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { formatDistanceToNow } from 'date-fns';

export default function ChatHistory() {
  const { chatHistory, loadChatFromHistory } = useApp();
  const [searchQuery, setSearchQuery] = useState('');

  const filteredHistory = chatHistory.filter((item) =>
    item.firstMessage.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getModeIcon = (mode: string) => {
    switch (mode) {
      case 'vector':
        return '🔍';
      case 'cascading':
        return '🔗';
      case 'deep-thinking':
        return '🧠';
      default:
        return '💬';
    }
  };

  return (
    <div className="flex-1 overflow-y-auto space-y-3">
      <div className="px-3 text-xs font-semibold text-white/40 uppercase tracking-wider">
        Recent Chats
      </div>

      {chatHistory.length > 0 && (
        <div className="px-3">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search conversations..."
            className="w-full bg-[#000000]/50 border border-[#2C2C2E] rounded-lg p-2 text-xs text-white placeholder-white/30 focus:outline-none focus:border-[#0A84FF]/50 focus:ring-1 focus:ring-[#0A84FF]/50"
          />
        </div>
      )}

      <div className="space-y-1 px-2">
        {filteredHistory.length > 0 ? (
          filteredHistory.map((item) => (
            <button
              key={item.id}
              onClick={() => loadChatFromHistory(item.id)}
              className="w-full text-left px-3 py-2.5 rounded-lg hover:bg-white/5 text-white/90 text-sm transition-colors group"
            >
              <div className="flex items-start gap-2">
                <span className="text-base mt-0.5">{getModeIcon(item.searchMode)}</span>
                <div className="flex-1 min-w-0">
                  <div className="truncate font-medium">
                    {item.firstMessage.slice(0, 40)}
                    {item.firstMessage.length > 40 ? '...' : ''}
                  </div>
                  <div className="text-xs text-white/40 mt-1 flex items-center gap-2">
                    <span>
                      {formatDistanceToNow(new Date(item.timestamp), { addSuffix: true })}
                    </span>
                    <span>•</span>
                    <span className="capitalize">{item.searchMode}</span>
                  </div>
                </div>
              </div>
            </button>
          ))
        ) : chatHistory.length > 0 ? (
          <div className="text-center text-white/40 text-sm py-4">
            No conversations match your search
          </div>
        ) : (
          <div className="text-center text-white/40 text-sm py-4">
            No chat history yet
          </div>
        )}
      </div>
    </div>
  );
}
