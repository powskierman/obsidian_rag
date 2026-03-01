'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { AppState, SearchMode, LLMProvider, SettingsState, ServicesStatus, Message, ChatHistoryItem, defaultSettings, defaultServices } from '../lib/types';
import { api } from '../lib/api';
import {
  getKnowledgeGraphServiceState,
  getLightRAGServiceState,
  getVectorServiceState,
} from '../lib/serviceStatus';

interface AppContextType extends AppState {
  setSearchMode: (mode: SearchMode) => void;
  setLLMProvider: (provider: LLMProvider) => void;
  updateSettings: (settings: Partial<SettingsState>) => void;
  updateServices: (services: Partial<ServicesStatus>) => void;
  addMessage: (message: Message) => void;
  clearMessages: () => void;
  setIsLoading: (loading: boolean) => void;
  saveChatToHistory: () => void;
  loadChatFromHistory: (id: string) => void;
  setSystemPrompt: (prompt: string) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);
const CURRENT_SETTINGS_VERSION = 2;
const VALID_LLM_PROVIDERS: LLMProvider[] = ['ollama', 'gemini', 'claude', 'openrouter', 'chatgpt', 'mlx'];

const clamp = (value: number, min: number, max: number): number => Math.min(max, Math.max(min, value));

const normalizeSettings = (raw: unknown): SettingsState => {
  const parsed = (raw && typeof raw === 'object') ? raw as Record<string, unknown> : {};
  const next: SettingsState = {
    ...defaultSettings,
    ...parsed,
  } as SettingsState;
  const rawSettingsVersion = Number(parsed.settingsVersion);
  const normalizedSettingsVersion = Number.isFinite(rawSettingsVersion) ? rawSettingsVersion : 0;
  const needsV2Reset = normalizedSettingsVersion < CURRENT_SETTINGS_VERSION;

  // Migration safety: old distanceThreshold values can map too aggressively.
  // Reset to 0% so users never get silently over-restrictive filtering.
  if (
    needsV2Reset &&
    (
      ('distanceThreshold' in parsed && !('relevanceThreshold' in parsed)) ||
      Number(next.relevanceThreshold) > 0
    )
  ) {
    console.warn('🔄 Settings migration v2 applied. Resetting relevanceThreshold to 0% to avoid restrictive filtering.');
    next.relevanceThreshold = 0;
  }

  const relevance = Number(next.relevanceThreshold);
  next.relevanceThreshold = Number.isFinite(relevance)
    ? clamp(Math.round(relevance), 0, 100)
    : defaultSettings.relevanceThreshold;

  const sources = Number(next.sources);
  next.sources = Number.isFinite(sources)
    ? clamp(Math.round(sources), 1, 50)
    : defaultSettings.sources;

  const temperature = Number(next.temperature);
  next.temperature = Number.isFinite(temperature)
    ? clamp(temperature, 0, 1)
    : defaultSettings.temperature;

  next.showSources = Boolean(next.showSources);
  next.enhancedSearch = Boolean(next.enhancedSearch);
  next.deepThinking = Boolean(next.deepThinking);
  next.settingsVersion = CURRENT_SETTINGS_VERSION;

  return next;
};

export function AppProvider({ children }: { children: ReactNode }) {
  const [searchMode, setSearchModeState] = useState<SearchMode>('hybrid');
  const [llmProvider, setLLMProvider] = useState<LLMProvider>('ollama');
  const [settings, setSettings] = useState<SettingsState>(defaultSettings);
  const [services, setServices] = useState<ServicesStatus>(defaultServices);
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentQuery, setCurrentQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState<ChatHistoryItem[]>([]);
  const [systemPrompt, setSystemPrompt] = useState('');

  // Load from localStorage on mount
  useEffect(() => {
    const previousOnError = window.onerror;
    const isExtensionContextError = (value: unknown): boolean =>
      typeof value === 'string' && value.includes('Extension context invalidated');

    // Prevent third-party extension reload noise from surfacing as uncaught app errors.
    window.onerror = (message, source, lineno, colno, error) => {
      if (isExtensionContextError(message) || isExtensionContextError(error?.message)) {
        return true;
      }
      if (typeof previousOnError === 'function') {
        return previousOnError(message, source, lineno, colno, error);
      }
      return false;
    };

    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      const reason = event.reason as { message?: unknown } | string | undefined;
      const reasonMessage =
        typeof reason === 'string'
          ? reason
          : typeof reason?.message === 'string'
            ? reason.message
            : '';
      if (isExtensionContextError(reasonMessage)) {
        event.preventDefault();
      }
    };
    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    const savedSettings = localStorage.getItem('obsidian-rag-settings');
    const savedHistory = localStorage.getItem('obsidian-rag-chat-history');
    const savedSearchMode = localStorage.getItem('obsidian-rag-search-mode');
    const savedProvider = localStorage.getItem('obsidian-rag-llm-provider');
    const savedPrompt = localStorage.getItem('obsidian-rag-system-prompt');
    let parsedSettings: SettingsState | null = null;

    if (savedSettings) {
      try {
        const parsed = JSON.parse(savedSettings);
        const normalized = normalizeSettings(parsed);
        setSettings(normalized);
        parsedSettings = normalized;
      } catch (e) {
        console.error('Failed to load settings:', e);
      }
    }

    if (savedHistory) {
      try {
        const history = JSON.parse(savedHistory);
        setChatHistory(history.map((item: any) => ({
          ...item,
          timestamp: new Date(item.timestamp)
        })));
      } catch (e) {
        console.error('Failed to load history:', e);
      }
    }

    if (parsedSettings?.deepThinking) {
      setSearchModeState('deep-thinking');
    } else if (savedSearchMode) {
      setSearchModeState(savedSearchMode as SearchMode);
    }

    if (savedProvider) {
      const normalizedProvider = savedProvider === 'perplexity'
        ? 'mlx'
        : VALID_LLM_PROVIDERS.includes(savedProvider as LLMProvider)
          ? savedProvider as LLMProvider
          : 'ollama';
      setLLMProvider(normalizedProvider);
    }

    if (savedPrompt) {
      setSystemPrompt(savedPrompt);
    }

    return () => {
      window.onerror = previousOnError;
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, []);

  // Save to localStorage when settings change
  useEffect(() => {
    localStorage.setItem('obsidian-rag-settings', JSON.stringify(settings));
  }, [settings]);

  useEffect(() => {
    localStorage.setItem('obsidian-rag-chat-history', JSON.stringify(chatHistory));
  }, [chatHistory]);

  useEffect(() => {
    localStorage.setItem('obsidian-rag-search-mode', searchMode);
  }, [searchMode]);

  useEffect(() => {
    localStorage.setItem('obsidian-rag-llm-provider', llmProvider);
  }, [llmProvider]);

  useEffect(() => {
    localStorage.setItem('obsidian-rag-system-prompt', systemPrompt);
  }, [systemPrompt]);

  const updateSettings = (newSettings: Partial<SettingsState>) => {
    const updated = { ...settings, ...newSettings, settingsVersion: CURRENT_SETTINGS_VERSION };
    if (updated.deepThinking) {
      updated.enhancedSearch = false;
    }
    console.log('⚙️ Settings updated:', updated);
    setSettings(updated);
  };

  const setSearchMode = (mode: SearchMode) => {
    setSearchModeState(mode);
    if (mode === 'deep-thinking') {
      setSettings((prev) => ({ ...prev, deepThinking: true, enhancedSearch: false }));
    } else {
      setSettings((prev) => ({ ...prev, deepThinking: false }));
    }
  };

  const updateServices = (newServices: Partial<ServicesStatus>) => {
    setServices(prev => ({
      ...prev,
      ...newServices
    }));
  };

  // Check services on mount
  useEffect(() => {
    const checkServices = async () => {
      try {
        const stats = await api.getStats();
        const ollamaModels = await api.getOllamaModels();
        const vectorStatus = getVectorServiceState(stats.documents);
        const knowledgeGraphStatus = getKnowledgeGraphServiceState(stats.graph);
        const lightragStatus = getLightRAGServiceState(stats.lightrag);

        updateServices({
          vectorDB: {
            available: vectorStatus === 'online',
            status: vectorStatus,
            chunks: stats.documents,
          },
          knowledgeGraph: {
            available: knowledgeGraphStatus === 'online',
            status: knowledgeGraphStatus,
            entities: stats.graph?.nodes || 0,
            relationships: stats.graph?.edges || 0,
          },
          lightrag: {
            available: lightragStatus === 'online',
            status: lightragStatus,
            nodes: stats.lightrag?.nodes || 0,
            edges: stats.lightrag?.edges || 0,
            indexed_notes: stats.lightrag?.indexed_notes || 0,
          },
          ollama: {
            available: ollamaModels.length > 0,
            models: ollamaModels,
          },
        });
      } catch (error) {
        console.error('Failed to check services on mount:', error);
        updateServices({
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
          lightrag: {
            available: false,
            status: 'offline',
            nodes: 0,
            edges: 0,
            indexed_notes: 0,
          },
          ollama: {
            available: false,
            models: [],
          },
        });
      }
    };

    checkServices();
  }, []);

  const addMessage = (message: Message) => {
    setMessages(prev => [...prev, message]);
  };

  const clearMessages = () => {
    setMessages([]);
  };

  const saveChatToHistory = () => {
    if (messages.length === 0) return;

    const firstUserMessage = messages.find(m => m.role === 'user');
    if (!firstUserMessage) return;

    const newHistoryItem: ChatHistoryItem = {
      id: Date.now().toString(),
      firstMessage: firstUserMessage.content,
      timestamp: new Date(),
      searchMode,
      messages,
    };

    setChatHistory(prev => {
      const updated = [newHistoryItem, ...prev];
      // Keep only last 50
      return updated.slice(0, 50);
    });
  };

  const loadChatFromHistory = (id: string) => {
    const historyItem = chatHistory.find(item => item.id === id);
    if (historyItem) {
      setMessages(historyItem.messages);
      setSearchMode(historyItem.searchMode);
    }
  };

  const value: AppContextType = {
    searchMode,
    llmProvider,
    settings,
    services,
    messages,
    currentQuery,
    isLoading,
    chatHistory,
    systemPrompt,
    setSearchMode,
    setLLMProvider,
    updateSettings,
    updateServices,
    addMessage,
    clearMessages,
    setIsLoading,
    saveChatToHistory,
    loadChatFromHistory,
    setSystemPrompt,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}
