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
  const { searchMode, setSearchMode, setResearchDepth, setDataSources, settings, llmProvider, setLLMProvider, services } = useApp();
  const [activePanel, setActivePanel] = useState<'search' | 'llm' | 'services' | 'settings' | 'actions' | null>(null);

  const getSearchModeLabel = () => {
    const labels: Record<string, string> = {
      'vector': 'Vector',
      'cascading': 'Cascading',
      'vault_review': 'Deep Review',
      'deep-thinking': 'Deep Thinking',
    };
    return labels[searchMode] || searchMode;
  };

  const getLLMProviderLabel = () => {
    const labels = {
      'ollama': 'Ollama',
      'gemini': 'Gemini Pro',
      'claude': 'Claude API',
      'openrouter': 'OpenRouter',
      'chatgpt': 'ChatGPT',
      'lmstudio': 'LM Studio'
    };
    return labels[llmProvider] || 'Ollama';
  };

  const getServicesStatus = () => {
    const activeCount = [
      services.vectorDB.available,
      services.knowledgeGraph.available,
      services.ollama.available,
      services.lmstudio.available,
    ].filter(Boolean).length;
    return `${activeCount}/4 Online`;
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
          currentDepth={settings.researchDepth ?? 'auto'}
          currentSources={settings.dataSources ?? ['vault']}
          onSelectMode={setSearchMode}
          onSelectDepth={setResearchDepth}
          onToggleSource={(src) => {
            const current = settings.dataSources ?? ['vault'];
            const next = current.includes(src) ? current.filter(s => s !== src) : [...current, src];
            setDataSources(next.length ? next : ['vault']);
          }}
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
