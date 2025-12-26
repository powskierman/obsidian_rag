'use client';

import React, { useState, useEffect } from 'react';
import { SearchBar } from '@/components/SearchBar';
import { KnowledgeGraph } from '@/components/KnowledgeGraph';
import { ChatSidebar, Message } from '@/components/ChatSidebar';
import { api, GraphEntity } from '@/lib/api';
import { SettingsModal } from '@/components/SettingsModal';

export default function Home() {
  const [entities, setEntities] = useState<GraphEntity[]>([]);
  const [messages, setMessages] = useState<Message[]>([
    { role: 'bot', text: "Welcome back, Michel. I've indexed 1,612 notes from your vault. Search anything to explore connections." }
  ]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [mainSource, setMainSource] = useState<string | null>(null);

  // Settings State
  const [showSettings, setShowSettings] = useState(false);
  const [searchMode, setSearchMode] = useState('hybrid'); // 'vector', 'graph', 'hybrid'
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const [model, setModel] = useState('anthropic/claude-haiku-4.5');
  const [sources, setSources] = useState(10);
  const [temperature, setTemperature] = useState(0.3);
  const [showSources, setShowSources] = useState(true);
  const [enhancedSearch, setEnhancedSearch] = useState(false);

  // ... (useEffect)

  const handleUnifiedSearch = async (query: string) => {
    if (!query) return;
    setSearchQuery(query);
    setMainSource(null); // Reset main source on new search

    // 1. Trigger UI states
    setIsSearching(true);
    setIsThinking(true);

    // 2. Add user query to chat Immediately
    setMessages(prev => [...prev, { role: 'user', text: query }]);

    try {
      const entityPromise = api.searchEntities(query, 15);
      const ragPromise = api.graphQuery(query, 20, searchMode, webSearchEnabled, model, sources, temperature, showSources, enhancedSearch);

      const [entityRes, ragRes] = await Promise.all([
        entityPromise.catch(e => ({ results: [] })),
        ragPromise.catch(e => ({ answer: "I couldn't generate a response." }))
      ]);

      const results = entityRes.results || [];
      setEntities(results);
      setMessages(prev => [...prev, { role: 'bot', text: ragRes.answer }]);

      // Check for exact match to find relevant note
      const exactMatch = results.find(e => e.name.toLowerCase() === query.toLowerCase());
      if (exactMatch && exactMatch.sources && exactMatch.sources.length > 0) {
        setMainSource(exactMatch.sources[0].filename);
      } else if (results.length > 0 && results[0].sources && results[0].sources.length > 0) {
        setMainSource(results[0].sources[0].filename);
      }

    } catch (e) {
      console.error('Unified search failed', e);
      setMessages(prev => [...prev, { role: 'bot', text: "Sorry, I encountered an error processing your request." }]);
    } finally {
      setIsSearching(false);
      setIsThinking(false);
    }
  };

  const handleClear = () => {
    if (confirm('Are you sure you want to clear the conversation?')) {
      setMessages([{ role: 'bot', text: "Conversation cleared. Ready for new queries." }]);
      setEntities([]);
      setMainSource(null);
    }
  };

  const handleExport = () => {
    const content = messages.map(m => `**${m.role.toUpperCase()}**: ${m.text}`).join('\n\n---\n\n');
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `obsidian-rag-export-${new Date().toISOString().slice(0, 10)}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <main className="main-app">
      {/* Header */}
      <header className="header">
        <div className="logo-container">
          <div className="logo-icon">💎</div>
          <h1 className="logo-text">Obsidian RAG</h1>
        </div>
        <nav className="top-nav">
          <button className="nav-btn active">Explorer</button>
          <button className="nav-btn">Vault</button>
          <button className="nav-btn" onClick={() => setShowSettings(true)}>Settings</button>
        </nav>
      </header>

      {/* Unified Prompt Bar */}
      <SearchBar
        onSearch={handleUnifiedSearch}
        isLoading={isSearching}
        placeholder={`Search (${searchMode}${webSearchEnabled ? ' + Web' : ''})...`}
        value={searchQuery}
      />

      {/* Primary Content Grid */}
      <section className="content-grid">
        <KnowledgeGraph
          entities={entities}
          onNodeClick={handleUnifiedSearch}
          mainSource={mainSource}
        />
        <ChatSidebar
          messages={messages}
          onSendMessage={() => { }}
          isThinking={isThinking}
          onClear={handleClear}
          onExport={handleExport}
          searchMode={searchMode}
          model={model}
          webSearchEnabled={webSearchEnabled}
        />
      </section>

      <SettingsModal
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
        searchMode={searchMode}
        setSearchMode={setSearchMode}
        webSearchEnabled={webSearchEnabled}
        setWebSearchEnabled={setWebSearchEnabled}
        model={model}
        setModel={setModel}
        sources={sources}
        setSources={setSources}
        temperature={temperature}
        setTemperature={setTemperature}
        showSources={showSources}
        setShowSources={setShowSources}
        enhancedSearch={enhancedSearch}
        setEnhancedSearch={setEnhancedSearch}
      />
    </main>
  );
}
<style jsx>{`
  .content-grid {
    display: grid;
    grid-template-columns: 1fr 450px;
    gap: 1.5rem;
    flex: 1;
    min-height: 0; /* Important for nested scrolling */
  }
  @media (max-width: 1024px) {
    .content-grid {
      grid-template-columns: 1fr;
    }
  }
`}</style>
