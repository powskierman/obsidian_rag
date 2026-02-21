import React, { useState } from 'react';
import { Source } from '../../lib/types';

interface SourcesDisplayProps {
  sources: Source[];
}

export default function SourcesDisplay({ sources }: SourcesDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const vaultName = 'Michel';
  const vaultRoot = '/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel';
  const hasUnsafeScheme = (value: string) => /^(javascript|data|vbscript):/i.test(value.trim());

  if (!sources || sources.length === 0) {
    return null;
  }

  const buildSourceLink = (source: Source) => {
    const filepath = source.filepath?.trim();
    if (filepath) {
      if (hasUnsafeScheme(filepath)) {
        return null;
      }
      const looksAbsolute = filepath.startsWith('/') || /^[A-Za-z]:[\\/]/.test(filepath);
      if (looksAbsolute) {
        if (filepath.startsWith(vaultRoot)) {
          const relPath = filepath.slice(vaultRoot.length).replace(/^\/+/, '');
          if (relPath) {
            return `obsidian://open?vault=${encodeURIComponent(vaultName)}&file=${encodeURIComponent(relPath)}`;
          }
        }
        return `obsidian://open?path=${encodeURIComponent(filepath)}`;
      }
    }
    const filename = source.filename?.trim();
    if (filename) {
      if (hasUnsafeScheme(filename)) {
        return null;
      }
      return `obsidian://search?vault=${encodeURIComponent(vaultName)}&query=${encodeURIComponent(filename)}`;
    }
    return null;
  };

  const safeFilename = (source: Source) => {
    if (source.filename?.trim()) return source.filename.trim();
    if (source.filepath?.trim()) return source.filepath.split('/').pop() || 'Unknown';
    return 'Unknown';
  };

  return (
    <div className="mt-4 pt-4 border-t border-[#2C2C2E]">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between text-sm font-medium text-white/60 hover:text-white transition-colors mb-3"
      >
        <span className="flex items-center gap-2">
          <span>📚</span>
          <span>Sources ({sources.length} documents)</span>
        </span>
        <svg
          className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isExpanded && (
        <div className="space-y-3">
          {sources.map((source, idx) => (
            <div
              key={idx}
              className="bg-[#1C1C1E] border border-[#2C2C2E] rounded-lg p-3 text-sm"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="font-medium text-white flex items-center gap-2">
                  <span className="text-white/40">{idx + 1}.</span>
                  {(() => {
                    const link = buildSourceLink(source);
                    if (!link) return <span>{source.filename}</span>;
                    return (
                      <a
                        href={link}
                        className="text-[#0A84FF] hover:text-[#6AB7FF] underline underline-offset-2"
                        title="Open in Obsidian"
                      >
                        {safeFilename(source)}
                      </a>
                    );
                  })()}
                </div>
                <span className="text-[#0A84FF] font-mono text-xs">
                  {(Number.isFinite(source.relevance) ? source.relevance : 50).toFixed(0)}%
                </span>
              </div>
              {source.filepath && (
                <div className="text-xs text-white/40 mb-2 font-mono truncate">
                  {source.filepath}
                </div>
              )}
              <div className="text-xs text-white/60 line-clamp-3">{source.snippet}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
