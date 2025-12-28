import { useState } from 'react';
import { useApp } from '../../context/AppContext';
import ConfigButton from './ConfigButton';
import SearchModePanel from './SearchModePanel';
import LLMProviderPanel from './LLMProviderPanel';
import ServicesPanel from './ServicesPanel';
import SettingsPanelModal from './SettingsPanelModal';
import EnhancedSearchToggle from './EnhancedSearchToggle';
import ActionsPanel from './ActionsPanel';

export default function ConfigurationPanel() {
  const { searchMode, setSearchMode, llmProvider, setLLMProvider, services } = useApp();
  const [activePanel, setActivePanel] = useState<'search' | 'llm' | 'services' | 'settings' | 'actions' | null>(null);

  const getSearchModeLabel = () => {
    const labels = {
      'vector': 'Vector',
      'knowledge-graph': 'Knowledge-Graph',
      'hybrid': 'Hybrid'
    };
    return labels[searchMode] || 'Hybrid';
  };

  const getLLMProviderLabel = () => {
    const labels = {
      'ollama': 'Ollama',
      'gemini': 'Gemini Pro',
      'claude': 'Claude API'
    };
    return labels[llmProvider] || 'Ollama';
  };

  const getServicesStatus = () => {
    const activeCount = [
      services.vectorDB.available,
      services.knowledgeGraph.available,
      services.ollama.available
    ].filter(Boolean).length;
    return `${activeCount}/3 Online`;
  };

  return (
    <>
      <div className="p-4 space-y-2">
        <div className="text-[10px] text-white/40 uppercase tracking-wider font-semibold mb-3 px-1">
          Configuration Panel
        </div>

        <ConfigButton
          icon="🔍"
          label="Search Mode"
          value={getSearchModeLabel()}
          onClick={() => setActivePanel('search')}
        />

        <ConfigButton
          icon="🤖"
          label="LLM Provider"
          value={getLLMProviderLabel()}
          onClick={() => setActivePanel('llm')}
        />

        <EnhancedSearchToggle />

        <ConfigButton
          icon="📊"
          label="Services"
          value={getServicesStatus()}
          onClick={() => setActivePanel('services')}
        />

        <ConfigButton
          icon="⚙️"
          label="Settings"
          value="Configure"
          onClick={() => setActivePanel('settings')}
        />

        <ConfigButton
          icon="💾"
          label="Actions"
          value="Manage"
          onClick={() => setActivePanel('actions')}
        />
      </div>

      {/* Panels */}
      {activePanel === 'search' && (
        <SearchModePanel
          currentMode={searchMode}
          onSelect={setSearchMode}
          onClose={() => setActivePanel(null)}
        />
      )}

      {activePanel === 'llm' && (
        <LLMProviderPanel
          currentProvider={llmProvider}
          onSelect={setLLMProvider}
          onClose={() => setActivePanel(null)}
        />
      )}

      {activePanel === 'services' && (
        <ServicesPanel onClose={() => setActivePanel(null)} />
      )}

      {activePanel === 'settings' && (
        <SettingsPanelModal onClose={() => setActivePanel(null)} />
      )}

      {activePanel === 'actions' && (
        <ActionsPanel onClose={() => setActivePanel(null)} />
      )}
    </>
  );
}
