import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface NoteViewerProps {
  filename: string;
  onClose: () => void;
}

export const NoteViewer: React.FC<NoteViewerProps> = ({ filename, onClose }) => {
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const fetchNote = async () => {
      try {
        setLoading(true);
        const data = await api.getNoteContent(filename);
        if (mounted) setContent(data.content);
      } catch (err) {
        if (mounted) setError('Failed to load note content');
      } finally {
        if (mounted) setLoading(false);
      }
    };
    fetchNote();
    return () => { mounted = false; };
  }, [filename]);

  return (
    <div className="note-viewer-overlay">
      <div className="note-viewer-panel glass-panel">
        <div className="note-header">
          <h3>{filename}</h3>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <div className="note-content-scroll">
          {loading ? (
            <div className="loading-state">Loading note...</div>
          ) : error ? (
            <div className="error-state">{error}</div>
          ) : (
            <div className="markdown-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>

      <style jsx>{`
        .note-viewer-overlay {
          position: fixed;
          top: 0;
          right: 0;
          bottom: 0;
          left: 0;
          z-index: 1000;
          background: rgba(0,0,0,0.5);
          display: flex;
          justify-content: flex-end;
          backdrop-filter: blur(2px);
        }
        .note-viewer-panel {
          width: 800px;
          max-width: 90vw;
          height: 100%;
          border-left: 1px solid rgba(255,255,255,0.1);
          background: rgba(10, 10, 15, 0.98);
          display: flex;
          flex-direction: column;
          animation: slideIn 0.3s ease-out;
          box-shadow: -10px 0 30px rgba(0,0,0,0.5);
        }
        @keyframes slideIn {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
        .note-header {
          padding: 1.5rem;
          border-bottom: 1px solid rgba(255,255,255,0.1);
          display: flex;
          justify-content: space-between;
          align-items: center;
          background: rgba(255,255,255,0.02);
        }
        .note-header h3 {
          margin: 0;
          font-weight: 500;
          color: #fff;
          font-family: 'Outfit', sans-serif;
        }
        .close-btn {
          background: none;
          border: none;
          color: rgba(255,255,255,0.6);
          font-size: 2rem;
          line-height: 1;
          cursor: pointer;
          padding: 0 0.5rem;
          transition: color 0.2s;
        }
        .close-btn:hover { color: white; }
        
        .note-content-scroll {
          flex: 1;
          overflow-y: auto;
          padding: 2.5rem;
        }
        
        .markdown-body {
          color: rgba(255,255,255,0.9);
          line-height: 1.7;
          font-size: 1rem;
          max-width: 100%;
        }
        
        /* Markdown Styles */
        .markdown-body :global(h1),
        .markdown-body :global(h2),
        .markdown-body :global(h3),
        .markdown-body :global(h4) {
          margin-top: 2em;
          margin-bottom: 0.8em;
          color: #fff;
          font-weight: 600;
          line-height: 1.3;
        }
        .markdown-body :global(h1) { font-size: 2em; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 0.3em; }
        .markdown-body :global(h2) { font-size: 1.6em; }
        .markdown-body :global(h3) { font-size: 1.3em; }
        
        .markdown-body :global(p) {
          margin-bottom: 1.2em;
        }
        
        .markdown-body :global(code) {
          background: rgba(255,255,255,0.1);
          padding: 0.2em 0.4em;
          border-radius: 4px;
          font-family: 'JetBrains Mono', monospace;
          font-size: 0.9em;
          color: #e2e8f0;
        }
        
        .markdown-body :global(pre) {
          background: #161b22;
          padding: 1.25rem;
          border-radius: 8px;
          overflow-x: auto;
          margin: 1.5rem 0;
          border: 1px solid rgba(255,255,255,0.1);
        }
        
        .markdown-body :global(pre code) {
          background: none;
          padding: 0;
          color: inherit;
          font-size: 0.9em;
        }
        
        .markdown-body :global(a) {
          color: #60a5fa;
          text-decoration: none;
          border-bottom: 1px solid transparent;
          transition: border-color 0.2s;
        }
        .markdown-body :global(a:hover) {
          border-bottom-color: #60a5fa;
        }
        
        .markdown-body :global(ul), 
        .markdown-body :global(ol) {
          padding-left: 1.5rem;
          margin-bottom: 1.2rem;
        }
        .markdown-body :global(li) {
          margin-bottom: 0.5em;
        }
        
        .markdown-body :global(blockquote) {
          border-left: 4px solid #3b82f6;
          padding: 0.8rem 1rem;
          margin: 1.5rem 0;
          background: rgba(59, 130, 246, 0.1);
          color: rgba(255,255,255,0.8);
          border-radius: 0 4px 4px 0;
        }
        
        .markdown-body :global(img) {
          max-width: 100%;
          border-radius: 8px;
          margin: 1rem 0;
          box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        
        .markdown-body :global(hr) {
          border: none;
          border-top: 1px solid rgba(255,255,255,0.1);
          margin: 2rem 0;
        }
        
        .markdown-body :global(table) {
          width: 100%;
          border-collapse: collapse;
          margin: 1.5rem 0;
        }
        .markdown-body :global(th), 
        .markdown-body :global(td) {
          padding: 0.75rem;
          border: 1px solid rgba(255,255,255,0.1);
          text-align: left;
        }
        .markdown-body :global(th) {
          background: rgba(255,255,255,0.05);
          font-weight: 600;
        }
        
        /* YAML Frontmatter styling - usually visually distinctive */
        .markdown-body :global(hr:first-child) + :global(p) {
           font-family: monospace;
           font-size: 0.85em;
           color: rgba(255,255,255,0.5);
        }

        .loading-state, .error-state {
          display: flex;
          align-items: center;
          justify-content: center;
          height: 100%;
          color: rgba(255,255,255,0.5);
          font-size: 1.1rem;
        }
        .error-state { color: #fe8c8c; }
        
        /* Custom Scrollbar */
        .note-content-scroll::-webkit-scrollbar {
          width: 8px;
        }
        .note-content-scroll::-webkit-scrollbar-track {
          background: rgba(0,0,0,0.2);
        }
        .note-content-scroll::-webkit-scrollbar-thumb {
          background: rgba(255,255,255,0.15);
          border-radius: 4px;
        }
        .note-content-scroll::-webkit-scrollbar-thumb:hover {
          background: rgba(255,255,255,0.25);
        }
      `}</style>
    </div>
  );
};
