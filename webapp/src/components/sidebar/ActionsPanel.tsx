import { useState } from 'react';
import { useApp } from '../../context/AppContext';

interface ActionsPanelProps {
  onClose: () => void;
}

export default function ActionsPanel({ onClose }: ActionsPanelProps) {
  const { messages, clearMessages, searchMode, settings, saveChatToHistory } = useApp();
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const handleExport = () => {
    // Generate markdown content
    const timestamp = new Date().toLocaleString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });

    const searchModeLabel = ({
      'vector': 'Vector',
      'knowledge-graph': 'Knowledge-Graph',
      'hybrid': 'Hybrid',
      'cascading': 'Cascading',
      'notes': 'Notes',
      'entities': 'Entities',
      'notes+vector': 'Notes+Vector',
      'entities+vector': 'Entities+Vector',
      'dual-graph': 'Dual-Graph'
    } as Record<string, string>)[searchMode] || searchMode;

    let markdown = `# Obsidian RAG Conversation\n`;
    markdown += `**Date:** ${timestamp}\n`;
    markdown += `**Search Mode:** ${searchModeLabel}\n`;
    markdown += `**Model:** ${settings.model}\n`;
    markdown += `\n---\n\n`;

    // Add all messages
    messages.forEach((msg, idx) => {
      if (idx > 0) markdown += `\n---\n\n`;

      markdown += `## ${msg.role === 'user' ? 'User' : 'Assistant'}\n`;
      markdown += `${msg.content}\n`;

      // Add sources if available
      if (msg.sources && msg.sources.length > 0) {
        markdown += `\n**Sources:**\n`;
        msg.sources.forEach((source, sourceIdx) => {
          markdown += `${sourceIdx + 1}. ${source.filename} (${Math.round(source.relevance)}% relevance)\n`;
          if (source.filepath) {
            markdown += `   ${source.filepath}\n`;
          }
        });
      }
    });

    // Create and download file
    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;

    const filename = `obsidian-rag-chat-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.md`;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    onClose();
  };

  const handleClearConfirm = () => {
    if (messages.length > 0) {
      saveChatToHistory();
    }
    clearMessages();
    setShowClearConfirm(false);
    onClose();
  };

  const handleClearCancel = () => {
    setShowClearConfirm(false);
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-[#1C1C1E] rounded-2xl border border-[#2C2C2E] p-6 w-[400px] max-w-[90vw]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-white">Actions</h2>
          <button
            onClick={onClose}
            className="text-white/40 hover:text-white/60 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {!showClearConfirm ? (
          <div className="space-y-3">
            {/* Export Button */}
            <button
              onClick={handleExport}
              disabled={messages.length === 0}
              className="w-full flex items-center gap-3 p-4 rounded-xl bg-[#2C2C2E] border border-[#3C3C3E] hover:border-[#0A84FF]/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:border-[#3C3C3E]"
            >
              <span className="text-2xl">💾</span>
              <div className="flex-1 text-left">
                <div className="text-sm font-medium text-white">Export Conversation</div>
                <div className="text-xs text-white/40 mt-0.5">
                  {messages.length === 0
                    ? 'No messages to export'
                    : `Download ${messages.length} message${messages.length === 1 ? '' : 's'} as markdown`
                  }
                </div>
              </div>
              <svg className="w-5 h-5 text-white/20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
            </button>

            {/* Clear Button */}
            <button
              onClick={() => setShowClearConfirm(true)}
              disabled={messages.length === 0}
              className="w-full flex items-center gap-3 p-4 rounded-xl bg-[#2C2C2E] border border-[#3C3C3E] hover:border-[#FF3B30]/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:border-[#3C3C3E]"
            >
              <span className="text-2xl">🗑️</span>
              <div className="flex-1 text-left">
                <div className="text-sm font-medium text-white">Clear Conversation</div>
                <div className="text-xs text-white/40 mt-0.5">
                  {messages.length === 0
                    ? 'No messages to clear'
                    : 'Delete all messages from current chat'
                  }
                </div>
              </div>
              <svg className="w-5 h-5 text-white/20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>

            <div className="mt-4 p-3 rounded-lg bg-[#2C2C2E]/50 border border-[#3C3C3E]">
              <div className="text-xs text-white/40">
                💡 Exported conversations are saved as markdown files to your Downloads folder.
              </div>
            </div>
          </div>
        ) : (
          // Clear Confirmation
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-[#FF3B30]/10 border border-[#FF3B30]/30">
              <div className="flex items-start gap-3">
                <span className="text-2xl">⚠️</span>
                <div>
                  <div className="text-sm font-medium text-white mb-1">
                    Clear Conversation?
                  </div>
                  <div className="text-xs text-white/60">
                    This will permanently delete all {messages.length} message{messages.length === 1 ? '' : 's'} from the current conversation. This action cannot be undone.
                  </div>
                </div>
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={handleClearCancel}
                className="flex-1 px-4 py-2.5 rounded-lg bg-[#2C2C2E] border border-[#3C3C3E] hover:border-[#0A84FF]/50 text-sm font-medium text-white transition-all"
              >
                Cancel
              </button>
              <button
                onClick={handleClearConfirm}
                className="flex-1 px-4 py-2.5 rounded-lg bg-[#FF3B30] hover:bg-[#FF3B30]/90 text-sm font-medium text-white transition-all"
              >
                Clear All
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
