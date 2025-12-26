'use client';

import React, { useState } from 'react';

interface SearchBarProps {
  onSearch: (query: string) => void;
  isLoading: boolean;
  placeholder?: string;
  value?: string;
}

export const SearchBar: React.FC<SearchBarProps> = ({ onSearch, isLoading, placeholder, value }) => {
  const [val, setVal] = useState(value || '');

  React.useEffect(() => {
    if (value !== undefined) {
      setVal(value);
    }
  }, [value]);

  return (
    <section className="search-container">
      <div className="search-wrapper">
        <div className={`glow-effect ${isLoading ? 'loading' : ''}`} />
        <input
          type="text"
          name="search-input"
          autoComplete="off"
          className="search-input"
          placeholder={placeholder || "Search your knowledge base..."}
          value={val}
          onChange={(e) => setVal(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') onSearch(val);
          }}
        />
        {isLoading && <div className="loader-dots"><span>.</span><span>.</span><span>.</span></div>}
      </div>
      <style jsx>{`
        .loading {
          animation: pulse-glow 1s infinite alternate !important;
          filter: blur(25px) !important;
        }
        .loader-dots {
          position: absolute;
          right: 25px;
          top: 50%;
          transform: translateY(-50%);
          color: var(--neon-blue);
          font-weight: bold;
          letter-spacing: 2px;
        }
        @keyframes pulse-glow {
          from { opacity: 0.5; }
          to { opacity: 1; box-shadow: 0 0 50px var(--neon-blue); }
        }
      `}</style>
    </section>
  );
};
