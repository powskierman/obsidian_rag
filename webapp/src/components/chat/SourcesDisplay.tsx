import React, { useEffect, useState } from 'react';
import { Source } from '../../lib/types';
import { api } from '../../lib/api';

interface SourcesDisplayProps {
  sources: Source[];
  retrievalIntent?: string;
}

export default function SourcesDisplay({ sources, retrievalIntent }: SourcesDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [showRelatedConnectionSources, setShowRelatedConnectionSources] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});
  const [vaultConfig, setVaultConfig] = useState({
    name: 'Michel',
    root: '/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel',
  });
  const hasUnsafeScheme = (value: string) => /^(javascript|data|vbscript):/i.test(value.trim());
  const hasWebScheme = (value: string) => /^https?:\/\//i.test(value.trim());
  const sourceTypeLabels: Record<string, string> = {
    'linked-note': 'Linked note',
    'direct-excerpt': 'Excerpt',
    'entity-context': 'Entity',
    'web-result': 'Web',
  };

  useEffect(() => {
    let active = true;

    api.getEnvConfig()
      .then((config) => {
        if (!active || !config?.vault) {
          return;
        }
        setVaultConfig((prev) => ({
          name: typeof config.vault?.name === 'string' && config.vault.name.trim() ? config.vault.name.trim() : prev.name,
          root: typeof config.vault?.root === 'string' && config.vault.root.trim() ? config.vault.root.trim() : prev.root,
        }));
      })
      .catch(() => {});

    return () => {
      active = false;
    };
  }, []);

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

  const categorizeSource = (source: Source) => {
    if (source.sourceCategory) return source.sourceCategory;
    const filepath = source.filepath?.trim() || '';
    return hasWebScheme(filepath) ? 'web' : 'vault';
  };

  const partitionSources = (items: Source[]) => ({
    vault: items.filter((source) => categorizeSource(source) === 'vault'),
    web: items.filter((source) => categorizeSource(source) === 'web'),
  });

  const sourceCardKey = (source: Source, idx: number) =>
    `${categorizeSource(source)}:${source.sourceType || 'unknown'}:${source.filepath || source.filename || 'unknown'}:${idx}`;

  const renderSourceCard = (source: Source, idx: number) => {
    const cardKey = sourceCardKey(source, idx);
    const isSnippetExpanded = Boolean(expandedSections[`${cardKey}:snippet`]);
    const snippet = source.snippet || '';
    const canExpandSnippet = snippet.length > 180;

    return (
      <div className="bg-[#1C1C1E] border border-[#2C2C2E] rounded-lg p-3 text-sm">
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
                  title={categorizeSource(source) === 'web' ? 'Open web source' : 'Open in Obsidian'}
                  target={categorizeSource(source) === 'web' ? '_blank' : undefined}
                  rel={categorizeSource(source) === 'web' ? 'noreferrer' : undefined}
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
        <div className={`text-xs text-white/60 whitespace-pre-wrap ${isSnippetExpanded ? '' : 'line-clamp-3'}`}>
          {snippet}
        </div>
        {canExpandSnippet && (
          <button
            onClick={() => toggleSection(`${cardKey}:snippet`)}
            className="mt-2 text-[11px] font-medium text-[#0A84FF] hover:text-[#6AB7FF]"
          >
            {isSnippetExpanded ? 'Show less' : 'Show more'}
          </button>
        )}
      </div>
    );
  };

  const buildSourceLink = (source: Source) => {
    const filepath = source.filepath?.trim();
    if (filepath) {
      if (hasUnsafeScheme(filepath)) {
        return null;
      }
      if (hasWebScheme(filepath)) {
        return filepath;
      }
      const looksAbsolute = filepath.startsWith('/') || /^[A-Za-z]:[\\/]/.test(filepath);
      if (looksAbsolute) {
        if (filepath.startsWith(vaultConfig.root)) {
          const relPath = filepath.slice(vaultConfig.root.length).replace(/^\/+/, '');
          if (relPath) {
            return `obsidian://open?vault=${encodeURIComponent(vaultConfig.name)}&file=${encodeURIComponent(relPath)}`;
          }
        }
        return `obsidian://open?path=${encodeURIComponent(filepath)}`;
      }
      return `obsidian://open?vault=${encodeURIComponent(vaultConfig.name)}&file=${encodeURIComponent(filepath)}`;
    }
    const filename = source.filename?.trim();
    if (filename) {
      if (hasUnsafeScheme(filename)) {
        return null;
      }
      if (hasWebScheme(filename)) {
        return filename;
      }
      return `obsidian://search?vault=${encodeURIComponent(vaultConfig.name)}&query=${encodeURIComponent(filename)}`;
    }
    return null;
  };

  const safeFilename = (source: Source) => {
    if (source.filename?.trim()) return source.filename.trim();
    if (source.filepath?.trim()) return source.filepath.split('/').pop() || 'Unknown';
    return 'Unknown';
  };

  const toggleSection = (key: string) => {
    setExpandedSections((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const renderSourceGroups = (items: Source[], keyPrefix: string) => {
    const groups = partitionSources(items);
    const sections = [
      { key: `${keyPrefix}-vault-sources`, title: 'Vault Sources', items: groups.vault, offset: 0 },
      { key: `${keyPrefix}-web-sources`, title: 'Web Sources', items: groups.web, offset: groups.vault.length },
    ].filter((section) => section.items.length > 0);

    if (sections.length === 0) {
      return null;
    }

    return (
      <div className="space-y-4">
        {sections.map((section) => {
          const visibleLimit = 6;
          const sectionExpanded = Boolean(expandedSections[section.key]);
          const visibleItems = sectionExpanded ? section.items : section.items.slice(0, visibleLimit);
          const hiddenCount = Math.max(0, section.items.length - visibleLimit);
          return (
          <div key={section.key} className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-white/45">
                {section.title}
              </h4>
              <span className="text-[11px] font-mono text-white/30">{section.items.length}</span>
            </div>
            {visibleItems.map((source, idx) => (
              <div key={sourceCardKey(source, section.offset + idx)}>
                {renderSourceCard(source, section.offset + idx)}
              </div>
            ))}
            {hiddenCount > 0 && (
              <button
                type="button"
                onClick={() => toggleSection(section.key)}
                className="text-xs text-[#0A84FF] hover:text-[#6AB7FF] transition-colors"
              >
                {sectionExpanded ? 'Show fewer' : `Show ${hiddenCount} more`}
              </button>
            )}
          </div>
        )})}
      </div>
    );
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
          {renderSourceGroups(primarySources, 'primary')}

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
                <div className="border-t border-[#2C2C2E] p-3">
                  {renderSourceGroups(secondarySources, 'secondary')}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
