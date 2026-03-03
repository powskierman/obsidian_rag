import React, { useState } from 'react';
import { Source } from '../../lib/types';

interface SourcesDisplayProps {
  sources: Source[];
  retrievalIntent?: string;
}

export default function SourcesDisplay({ sources, retrievalIntent }: SourcesDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [showRelatedConnectionSources, setShowRelatedConnectionSources] = useState(false);
  const vaultName = 'Michel';
  const vaultRoot = '/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel';
  const hasUnsafeScheme = (value: string) => /^(javascript|data|vbscript):/i.test(value.trim());
  const sourceTypeLabels: Record<string, string> = {
    'linked-note': 'Linked note',
    'direct-excerpt': 'Excerpt',
    'entity-context': 'Entity',
  };

  if (!sources || sources.length === 0) {
    return null;
  }

  const isConnectionView = retrievalIntent === 'connection';
  const isExplicitPathSource = (source: Source) =>
    /explicit graph path/i.test(source.snippet || '') || source.relevance > 72;
  const primarySources = isConnectionView
    ? sources.filter((source) => isExplicitPathSource(source))
    : sources;
  const secondarySources = isConnectionView
    ? sources.filter((source) => !isExplicitPathSource(source))
    : [];

  const renderSourceCard = (source: Source, idx: number) => (
    <div
      key={`${source.filepath || source.filename}-${idx}`}
      className="bg-[#1C1C1E] border border-[#2C2C2E] rounded-lg p-3 text-sm"
    >
      <div className="flex items-start justify-between mb-2">
        <div className="font-medium text-white flex items-center gap-2 flex-wrap">
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
          {source.sourceType && sourceTypeLabels[source.sourceType] && (
            <span className="px-2 py-0.5 rounded-full border border-white/10 text-[10px] uppercase tracking-[0.12em] text-white/45">
              {sourceTypeLabels[source.sourceType]}
            </span>
          )}
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
  );

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
          {primarySources.map((source, idx) => renderSourceCard(source, idx))}

          {isConnectionView && secondarySources.length > 0 && (
            <div className="rounded-lg border border-[#2C2C2E] bg-[#14161A] overflow-hidden">
              <button
                onClick={() => setShowRelatedConnectionSources(!showRelatedConnectionSources)}
                className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-white/55 hover:text-white transition-colors"
              >
                <span>Related but not on returned path ({secondarySources.length})</span>
                <svg
                  className={`w-4 h-4 transition-transform ${showRelatedConnectionSources ? 'rotate-180' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {showRelatedConnectionSources && (
                <div className="border-t border-[#2C2C2E] p-3 space-y-3">
                  {secondarySources.map((source, idx) => renderSourceCard(source, primarySources.length + idx))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
