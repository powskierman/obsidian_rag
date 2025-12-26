import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ThinkingIndicator } from './ThinkingIndicator';

export interface Message {
  role: 'bot' | 'user';
  text: string;
}

interface ChatSidebarProps {
  messages: Message[];
  onSendMessage: (msg: string) => void;
  isThinking: boolean;
  onClear: () => void;
  onExport: () => void;
  // New props for thinking state
  searchMode: string;
  model: string;
  webSearchEnabled: boolean;
}

export const ChatSidebar: React.FC<ChatSidebarProps> = ({
  messages,
  onSendMessage,
  isThinking,
  onClear,
  onExport,
  searchMode,
  model,
  webSearchEnabled
}) => {
  const [input, setInput] = React.useState('');

  const handleSend = () => {
    if (!input.trim() || isThinking) return;
    onSendMessage(input);
    setInput('');
  };

  return (
    <aside className="glass-panel chat-sidebar">
      <div className="panel-header">
        <h3>AI Assistant</h3>
        {/* Removed header timer in favor of inline detailed indicator */}
      </div>
      <div className="messages-area">
        {messages.map((m, i) => (
          <div key={i} className={`msg-group ${m.role}-msg-group`}>
            {m.role === 'bot' && <div className="bot-avatar">✨</div>}
            <div className={`${m.role}-bubble`}>
              {m.role === 'bot' ? (
                <div className="markdown-content">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {m.text}
                  </ReactMarkdown>

                  {/* Feedback UI */}
                  <div className="feedback-actions">
                    <span className="feedback-label">Rate this response:</span>
                    <div className="feedback-buttons">
                      <button className="feedback-btn" title="Poor">😞</button>
                      <button className="feedback-btn" title="Fair">😕</button>
                      <button className="feedback-btn" title="OK">😐</button>
                      <button className="feedback-btn" title="Good">😊</button>
                      <button className="feedback-btn" title="Excellent">😍</button>
                    </div>
                  </div>

                  {/* Action Footer */}
                  <div className="sidebar-footer">
                    <button className="action-btn" onClick={onExport} title="Export Conversation">
                      💾 Export
                    </button>
                    <button className="action-btn" onClick={onClear} title="Clear Conversation">
                      🗑️ Clear
                    </button>
                  </div>

                </div>
              ) : (
                m.text
              )}
            </div>
          </div>
        ))}
        {isThinking && (
          <div className="msg-group bot-msg-group">
            <div className="bot-avatar">✨</div>
            <div className="bot-bubble thinking-container">
              <ThinkingIndicator
                searchMode={searchMode}
                model={model}
                webSearchEnabled={webSearchEnabled}
              />
            </div>
          </div>
        )}
      </div>
      <style jsx>{`
        .chat-sidebar {
          display: flex;
          flex-direction: column;
          height: 100%;
          overflow: hidden;
        }
        .panel-header {
          padding: 1rem 1.2rem;
          border-bottom: 1px solid rgba(255,255,255,0.05);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .messages-area {
          flex: 1;
          overflow-y: auto;
          padding: 1rem;
          display: flex;
          flex-direction: column;
        }
        .msg-group { display: flex; gap: 0.8rem; margin-bottom: 1rem; }
        .user-msg-group { justify-content: flex-end; }
        .user-bubble {
          background: var(--grad-primary);
          padding: 0.8rem 1.2rem;
          border-radius: 18px 18px 0 18px;
          font-size: 0.9rem;
          color: white;
          max-width: 85%;
        }
        /* Bot bubble style for thinking container - can be transparent or subtle */
        .bot-bubble.thinking-container {
          background: rgba(255,255,255,0.05);
          border: 1px solid rgba(255,255,255,0.1);
          padding: 0.8rem 1.2rem;
          border-radius: 0 18px 18px 18px;
        }

        /* Markdown Styles */
        .markdown-content {
          line-height: 1.6;
        }
        .markdown-content p {
          margin-bottom: 0.8rem;
        }
        .markdown-content h1, .markdown-content h2, .markdown-content h3 {
          margin-top: 1rem;
          margin-bottom: 0.5rem;
          font-weight: 600;
          color: #fff;
        }
        .markdown-content ul, .markdown-content ol {
          margin-left: 1.5rem;
          margin-bottom: 1rem;
        }
        .markdown-content li {
          margin-bottom: 0.3rem;
        }
        .markdown-content table {
          border-collapse: collapse;
          width: 100%;
          margin: 1rem 0;
          font-size: 0.85rem;
          background: rgba(255,255,255,0.05);
          border-radius: 8px;
          overflow: hidden;
        }
        .markdown-content th, .markdown-content td {
          text-align: left;
          padding: 0.8rem;
          border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .markdown-content th {
          background: rgba(255,255,255,0.1);
          font-weight: 600;
          color: var(--neon-blue);
        }
        .markdown-content code {
          background: rgba(0,0,0,0.3);
          padding: 0.2rem 0.4rem;
          border-radius: 4px;
          font-family: monospace;
          font-size: 0.9em;
        }
        .markdown-content pre {
          background: rgba(0,0,0,0.3);
          padding: 1rem;
          border-radius: 8px;
          overflow-x: auto;
          margin-bottom: 1rem;
        }
        .markdown-content pre code {
          background: none;
          padding: 0;
        }
        .markdown-content a {
          color: var(--neon-blue);
          text-decoration: none;
        }
        .markdown-content a:hover {
          text-decoration: underline;
        }
        
        /* Feedback Actions */
        .feedback-actions {
          margin-top: 1rem;
          padding-top: 0.8rem;
          border-top: 1px solid rgba(255,255,255,0.1);
          display: flex;
          align-items: center;
          gap: 1rem;
          opacity: 0.7;
          transition: opacity 0.2s;
        }
        .feedback-actions:hover {
          opacity: 1;
        }
        .feedback-label {
          font-size: 0.75rem;
          color: rgba(255,255,255,0.5);
        }
        .feedback-buttons {
          display: flex;
          gap: 0.5rem;
        }
        .feedback-btn {
          background: none;
          border: none;
          font-size: 1.1rem;
          cursor: pointer;
          transition: transform 0.2s;
          padding: 0 2px;
          opacity: 0.6;
        }
        .feedback-btn:hover {
          transform: scale(1.2);
          opacity: 1;
        }
        .markdown-content a:hover {
          text-decoration: underline;
        }

        .sidebar-footer {
            padding: 1rem;
            border-top: 1px solid rgba(255,255,255,0.05);
            display: flex;
            gap: 1rem;
            justify-content: center;
        }
        .action-btn {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            color: rgba(255,255,255,0.8);
            padding: 0.6rem 1rem;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .action-btn:hover {
            background: rgba(255,255,255,0.15);
            color: white;
            border-color: rgba(255,255,255,0.3);
        }
      `}</style>
    </aside>
  );
};
