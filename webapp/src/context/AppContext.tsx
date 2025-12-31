'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { AppState, SearchMode, LLMProvider, SettingsState, ServicesStatus, Message, ChatHistoryItem, defaultSettings, defaultServices } from '../lib/types';
import { api } from '../lib/api';

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

export function AppProvider({ children }: { children: ReactNode }) {
  const [searchMode, setSearchMode] = useState<SearchMode>('hybrid');
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
    const savedSettings = localStorage.getItem('obsidian-rag-settings');
    const savedHistory = localStorage.getItem('obsidian-rag-chat-history');
    const savedSearchMode = localStorage.getItem('obsidian-rag-search-mode');
    const savedProvider = localStorage.getItem('obsidian-rag-llm-provider');
    const savedPrompt = localStorage.getItem('obsidian-rag-system-prompt');

    if (savedSettings) {
      try {
        setSettings(JSON.parse(savedSettings));
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

    if (savedSearchMode) {
      setSearchMode(savedSearchMode as SearchMode);
    }

    if (savedProvider) {
      setLLMProvider(savedProvider as LLMProvider);
    }

    if (savedPrompt) {
      setSystemPrompt(savedPrompt);
    }
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
    setSettings(prev => ({ ...prev, ...newSettings }));
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

        updateServices({
          vectorDB: {
            available: stats.documents > 0,
            chunks: stats.documents,
          },
          knowledgeGraph: {
            available: stats.graph !== null && (stats.graph.nodes > 0 || stats.graph.graph_loaded === true),
            entities: stats.graph?.nodes || 0,
            relationships: stats.graph?.edges || 0,
          },
          ollama: {
            available: ollamaModels.length > 0,
            models: ollamaModels,
          },
        });
      } catch (error) {
        console.error('Failed to check services on mount:', error);
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
