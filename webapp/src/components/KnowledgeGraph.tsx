'use client';

import React from 'react';

interface KnowledgeGraphProps {
  entities: any[];
  onNodeClick: (query: string) => void;
  mainSource?: string | null;
}

export const KnowledgeGraph: React.FC<KnowledgeGraphProps> = ({ entities, onNodeClick, mainSource }) => {
  // Deduplicate entities (case-insensitive + ignore punctuation)
  const uniqueEntities = React.useMemo(() => {
    const seen = new Set<string>();
    return entities.filter(ent => {
      if (!ent.name) return false;
      const key = ent.name.toLowerCase().replace(/[^a-z0-9]/g, '');

      // If empty key (e.g. only symbols), look at raw name or skip? 
      // Fallback to raw lowercase if normalized is empty
      const finalKey = key || ent.name.toLowerCase();

      if (seen.has(finalKey)) return false;
      seen.add(finalKey);
      return true;
    });
  }, [entities]);

  return (
    <div className="glass-panel graph-panel">
      <div className="panel-header">
        <h3>Knowledge Graph</h3>
        <div className="header-controls">
          <span className="badge">{uniqueEntities.length > 0 ? 'Live View' : 'Idle'}</span>
        </div>
      </div>
      <div className="graph-content">
        {uniqueEntities.length === 0 ? (
          <div className="empty-state">
            <p>Perform a search to visualize connections</p>
          </div>
        ) : (
          <div className="dynamic-nodes">
            {uniqueEntities.map((ent, i) => {
              return (
                <div
                  key={ent.name}
                  onClick={() => onNodeClick(ent.name)}
                  className={`node-blob ${i % 3 === 0 ? 'purple' : i % 3 === 1 ? 'blue' : 'cyan'}`}
                  style={{
                    animationDelay: `${i * 0.1}s` // Stagger animations slightly
                  }}
                >
                  {ent.name}
                </div>
              );
            })}
          </div>
        )}
      </div>
      <style jsx>{`
        .empty-state {
          display: flex;
          align-items: center;
          justify-content: center;
          height: 100%;
          color: rgba(255,255,255,0.3);
          font-style: italic;
        }
        .dynamic-nodes {
          display: flex;
          flex-wrap: wrap;
          justify-content: center;
          align-items: center;
          gap: 1.5rem; /* Ensure plenty of space between pills */
          padding: 2rem;
          height: 100%;
          width: 100%;
          overflow-y: auto; /* Allow scrolling if many nodes */
        }
        .header-controls {
          display: flex;
          align-items: center;
          gap: 1rem;
        }
        .source-btn {
          background: rgba(0, 210, 255, 0.1);
          border: 1px solid var(--neon-blue);
          color: var(--neon-blue);
          padding: 0.3rem 0.8rem;
          border-radius: 8px;
          cursor: pointer;
          font-size: 0.8rem;
          font-weight: 600;
          transition: all 0.2s;
        }
        .source-btn:hover {
          background: var(--neon-blue);
          color: black;
          box-shadow: 0 0 10px var(--neon-blue);
        }
      `}</style>
    </div>
  );
};
