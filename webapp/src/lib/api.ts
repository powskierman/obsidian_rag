const resolveUrl = (envVal: string | undefined, defaultPort: string, isWs = false) => {
  if (envVal && !envVal.includes('localhost') && !envVal.includes('127.0.0.1')) {
    return envVal;
  }
  if (typeof window !== 'undefined') {
    const protocol = isWs ? (window.location.protocol === 'https:' ? 'wss:' : 'ws:') : window.location.protocol;
    return `${protocol}//${window.location.hostname}:${defaultPort}`;
  }
  return envVal || (isWs ? `ws://127.0.0.1:${defaultPort}` : `http://127.0.0.1:${defaultPort}`);
};

const WS_GATEWAY_URL = resolveUrl(process.env.NEXT_PUBLIC_WS_GATEWAY_URL, '4000', true);

const tryFetchJson = async (url: string): Promise<any | null> => {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      return null;
    }
    return await response.json();
  } catch {
    return null;
  }
};

export interface SearchResult {
  filename: string;
  filepath: string;
  relevance: number;
  snippet: string;
  sourceType?: 'linked-note' | 'direct-excerpt' | 'entity-context' | 'web-result';
  sourceCategory?: 'vault' | 'web';
}

export interface GraphResponse {
  answer: string;
  query: string;
}

const normalizeSource = (source: any): SearchResult => {
  const filepath = source?.filepath || source?.file_path || 'unknown';
  const filename = source?.filename || (typeof filepath === 'string' ? filepath.split('/').pop() : 'unknown') || 'unknown';
  const rawRelevance = source?.relevance;
  const relevance = Number.isFinite(rawRelevance)
    ? Number(rawRelevance)
    : Number.isFinite(Number(rawRelevance))
      ? Number(rawRelevance)
      : 50;
  const snippet = source?.snippet || source?.content || '';
  return {
    filename,
    filepath,
    relevance,
    snippet,
    sourceType: source?.sourceType || source?.source_type,
    sourceCategory: source?.sourceCategory || source?.source_category,
  };
};



export const api = {
  unifiedSearch: async (
    query: string,
    mode: 'vector' | 'cascading' = 'cascading',
    n_results = 10,
    llm_provider = 'ollama',
    model = '',
    temperature = 0.7,
    relevance_threshold = 0,  // 0-100%, 0 = show all results
    enhanced_search = false,
    brief_concept_index = true,
    system_prompt = ''
  ): Promise<{
    answer: string;
    sources?: SearchResult[];
    extracted_entities?: string[];
    retrievalIntent?: string;
    llm_provider?: string;
    model?: string;
    web_search?: any;
    llm_knowledge?: any;
  }> => {
    try {
      const enableWebSearch = enhanced_search;
      const enableLlmKnowledge = enhanced_search;
      const requestBody = {
        query,
        mode,
        max_results: n_results,
        llm_provider,
        model,
        temperature,
        relevance_threshold,
        web_search: enableWebSearch,
        llm_knowledge: enableLlmKnowledge,
        brief_concept_index,
        system_prompt: system_prompt || null
      };
      console.log('🌐 API request body:', requestBody);

      // Use the new unified query endpoint
      const response = await fetch('/api/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Unified query failed:', response.status, errorText);
        throw new Error(`Unified query failed: ${response.status} ${errorText}`);
      }

      const data = await response.json();

      if (mode === 'vector') {
        const vectorData = data.results || data;
        let sources: SearchResult[] = Array.isArray(data.sources)
          ? data.sources.map(normalizeSource)
          : [];

        if (sources.length === 0 && vectorData.documents && vectorData.documents[0]) {
          sources = vectorData.documents[0].map((doc: string, i: number) => {
            const dist = vectorData.distances[0][i];
            const relevance = dist !== undefined
              ? Math.max(0, Math.min(100, 100 / (1 + Math.exp(dist / 2))))
              : 50;

            return {
              filename: vectorData.metadatas[0][i]?.filename || 'unknown',
              filepath: vectorData.metadatas[0][i]?.filepath || 'unknown',
              relevance,
              snippet: doc
            };
          });
        }

        return {
          answer: typeof data.answer === 'string' && data.answer.trim()
            ? data.answer
            : (sources.length > 0 ? `Found ${sources.length} matching snippets in your vault.` : 'No results found'),
          sources,
          web_search: data.web_search,
          llm_knowledge: data.llm_knowledge,
        };
      } else if (mode === 'cascading') {
        return {
          answer: data.answer || 'No results found',
          sources: (data.sources || []).map(normalizeSource),
          extracted_entities: data.results?.entities || [],
          retrievalIntent: data.retrieval_intent || data.results?.retrieval_intent,
          web_search: data.web_search,
          llm_knowledge: data.llm_knowledge,
        };
      } else {
        return {
          answer: 'Unsupported mode.',
          sources: []
        };
      }
    } catch (error) {
      console.error('Unified search error:', error);
      throw error;
    }
  },

  getStats: async () => {
    const gatewayData = await tryFetchJson('/api/stats');
    return {
      documents: gatewayData?.documents || 0,
      graph: gatewayData?.graph || null,
      lightrag: gatewayData?.lightrag || null
    };
  },

  getOllamaModels: async (): Promise<string[]> => {
    try {
      const response = await fetch('/api/ollama/models');
      if (!response.ok) {
        return [];
      }
      const data = await response.json();
      return Array.isArray(data?.models) ? data.models : [];
    } catch (error) {
      console.log('Ollama model discovery failed via webapp proxy. Returning empty model list.');
      return [];
    }
  },

  submitFeedback: async (feedback: any): Promise<void> => {
    // Placeholder: feedback endpoint logic not yet in unified gateway V1 spec shown in context.
    // Leaving as no-op or direct call if service available.
    // Future: POST ${GATEWAY_URL}/api/v1/feedback
    console.log("Feedback not yet implemented in V1 Gateway", feedback);
  },

  checkApiKeys: async (): Promise<{ gemini: boolean; anthropic: boolean; openai: boolean }> => {
    const config = await api.getEnvConfig();
    return {
      gemini: config.keys.gemini,
      anthropic: config.keys.anthropic,
      openai: config.keys.openai,
    };
  },

  getEnvConfig: async (): Promise<{ keys: { gemini: boolean; anthropic: boolean; openai: boolean; lmstudio: boolean }; models: Record<string, string> }> => {
    try {
      let response = await fetch('/api/provider-status');
      if (!response.ok) {
        response = await fetch('/api/env-config');
      }
      if (!response.ok) {
        return {
          keys: { gemini: false, anthropic: false, openai: false, lmstudio: false },
          models: {}
        };
      }
      return await response.json();
    } catch (error) {
      console.error('Failed to get env config:', error);
      return {
        keys: { gemini: false, anthropic: false, openai: false, lmstudio: false },
        models: {}
      };
    }
  },

  // WebSocket URL for Deep Thinking
  deepResearchEndpoint: `${WS_GATEWAY_URL}/api/v1/deep-research`
};
