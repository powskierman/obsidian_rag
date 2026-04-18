// Type definitions for Obsidian RAG webapp
import { DataServiceState } from './serviceStatus';

// Canonical search modes — Ask / Research / Investigate
// Legacy names (vector, cascading, vault_review, mempalace) accepted by the
// backend during the deprecation window but no longer surfaced in the UI.
export type SearchMode = 'ask' | 'research' | 'investigate';

// Research depth — only relevant when mode === 'research'.
export type ResearchDepth = 'auto' | 'shallow' | 'staged' | 'full';

// Data sources queried in parallel per request.
export type DataSource = 'vault' | 'mempalace' | 'web';

export type LLMProvider = 'ollama' | 'gemini' | 'claude' | 'openrouter' | 'chatgpt' | 'lmstudio';

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  retrievalIntent?: string;
  enhancedSearch?: EnhancedSearchData;
  queryId?: string;
  rating?: number;
  timestamp?: string;
}

export interface Source {
  filename: string;
  filepath: string;
  relevance: number;
  snippet: string;
  sourceType?: 'linked-note' | 'direct-excerpt' | 'entity-context' | 'web-result';
  sourceCategory?: 'vault' | 'web';
}

export interface EnhancedSearchData {
  llmKnowledge?: string;
  webResults?: WebSearchResult[];
  webSearchTerms?: string;
  webStatus?: string;
}

export interface WebSearchResult {
  title: string;
  url: string;
  snippet: string;
}

export interface SettingsState {
  settingsVersion?: number;
  model: string;
  providerModels?: Partial<Record<LLMProvider, string>>;
  sources: number;            // max results (n_results)
  dataSources: DataSource[];  // which indexes to query
  researchDepth: ResearchDepth;
  temperature: number;
  relevanceThreshold: number;  // 0-100%, 0 = show all
  showSources: boolean;
  enhancedSearch: boolean;
  briefConceptIndex: boolean;
  deepThinking: boolean;       // kept for compat; derived from searchMode === 'investigate'
}

export interface ServicesStatus {
  vectorDB: {
    available: boolean;
    status: DataServiceState;
    chunks: number;
  };
  knowledgeGraph: {
    available: boolean;
    status: DataServiceState;
    entities: number;
    relationships: number;
  };
  lightrag?: {
    available: boolean;
    status: DataServiceState;
    nodes: number;
    edges: number;
    indexed_notes?: number;
  };
  ollama: {
    available: boolean;
    models: string[];
  };
  lmstudio: {
    available: boolean;
    models: string[];
  };
}

export interface ChatHistoryItem {
  id: string;
  firstMessage: string;
  timestamp: Date;
  searchMode: SearchMode;
  messages: Message[];
}

export interface AppState {
  searchMode: SearchMode;
  llmProvider: LLMProvider;
  settings: SettingsState;
  services: ServicesStatus;
  messages: Message[];
  currentQuery: string;
  isLoading: boolean;
  chatHistory: ChatHistoryItem[];
  systemPrompt: string;
}

export const defaultSettings: SettingsState = {
  settingsVersion: 5,
  model: 'llama3.2:latest',
  providerModels: {},
  sources: 10,
  dataSources: ['vault'],
  researchDepth: 'auto',
  temperature: 0.3,
  relevanceThreshold: 0,
  showSources: true,
  enhancedSearch: false,
  briefConceptIndex: true,
  deepThinking: false,
};

export const defaultServices: ServicesStatus = {
  vectorDB: {
    available: false,
    status: 'offline',
    chunks: 0,
  },
  knowledgeGraph: {
    available: false,
    status: 'offline',
    entities: 0,
    relationships: 0,
  },
  ollama: {
    available: false,
    models: [],
  },
  lmstudio: {
    available: false,
    models: [],
  },
};

// Migration helper — maps stored legacy mode names to canonical.
export const LEGACY_SEARCH_MODE_MAP: Record<string, SearchMode> = {
  vector: 'ask',
  mempalace: 'ask',
  cascading: 'research',
  vault_review: 'research',
  hybrid: 'research',
  'deep-thinking': 'investigate',
  'deep-research': 'investigate',
  'knowledge-graph': 'research',
  notes: 'research',
  entities: 'research',
  'notes+vector': 'research',
  'entities+vector': 'research',
  'dual-graph': 'research',
};
