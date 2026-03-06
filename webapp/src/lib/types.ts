// Type definitions for Obsidian RAG webapp
import { DataServiceState } from './serviceStatus';

// Search modes matching backend API
export type SearchMode =
  // Single-source modes
  | 'vector'          // Pure vector similarity (ChromaDB)
  | 'hybrid'          // Graph + vector search
  // Agentic and pipeline modes
  | 'cascading'       // 5-Stage Waterfall
  | 'deep-thinking';  // Agentic reasoning mode

export type LLMProvider = 'ollama' | 'gemini' | 'claude' | 'openrouter' | 'chatgpt' | 'mlx';

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
}

export interface WebSearchResult {
  title: string;
  url: string;
  snippet: string;
}

export interface SettingsState {
  settingsVersion?: number;
  model: string;
  sources: number;
  temperature: number;
  relevanceThreshold: number;  // 0-100%, 0 = show all
  showSources: boolean;
  enhancedSearch: boolean;
  deepThinking: boolean;
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
  settingsVersion: 2,
  model: 'llama3.2:latest',
  sources: 10,
  temperature: 0.3,
  relevanceThreshold: 0,  // 0-100%, 0 = show all results
  showSources: true,
  enhancedSearch: false,
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
};
