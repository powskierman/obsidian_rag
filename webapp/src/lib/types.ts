// Type definitions for Obsidian RAG webapp

// Search modes matching backend API
export type SearchMode =
  // Single-source modes
  | 'vector'          // Pure vector similarity (ChromaDB)
  | 'notes'           // Note-centric graph (NetworkX)
  | 'entities'        // Entity-centric graph (LightRAG)
  // Dual-source modes
  | 'notes+vector'    // NetworkX + ChromaDB
  | 'entities+vector' // LightRAG + ChromaDB
  | 'dual-graph'      // NetworkX + LightRAG
  // Ultimate hybrid
  | 'hybrid'          // All three sources
  // New experimental modes
  | 'cascading';      // 5-Stage Waterfall

export type LLMProvider = 'ollama' | 'gemini' | 'claude';

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
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
  model: string;
  sources: number;
  temperature: number;
  showSources: boolean;
  enhancedSearch: boolean;
  deepThinking: boolean;
}

export interface ServicesStatus {
  vectorDB: {
    available: boolean;
    chunks: number;
  };
  knowledgeGraph: {
    available: boolean;
    entities: number;
    relationships: number;
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
  model: 'llama3.2:latest',
  sources: 10,
  temperature: 0.3,
  showSources: true,
  enhancedSearch: false,
  deepThinking: false,
};

export const defaultServices: ServicesStatus = {
  vectorDB: {
    available: false,
    chunks: 0,
  },
  knowledgeGraph: {
    available: false,
    entities: 0,
    relationships: 0,
  },
  ollama: {
    available: false,
    models: [],
  },
};
