const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL || 'http://127.0.0.1:4000';
const WS_GATEWAY_URL = process.env.NEXT_PUBLIC_WS_GATEWAY_URL || 'ws://127.0.0.1:4000';
const EMBEDDING_URL = process.env.NEXT_PUBLIC_EMBEDDING_URL || 'http://127.0.0.1:8000';
const GRAPH_URL = process.env.NEXT_PUBLIC_GRAPH_URL || 'http://127.0.0.1:8002';

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
}

export interface GraphResponse {
  answer: string;
  query: string;
}

export const api = {
  unifiedSearch: async (
    query: string,
    mode: 'vector' | 'notes' | 'entities' | 'notes+vector' | 'entities+vector' | 'dual-graph' | 'hybrid' | 'cascading' = 'hybrid',
    n_results = 10,
    llm_provider = 'ollama',
    model = '',
    temperature = 0.7,
    relevance_threshold = 0,  // 0-100%, 0 = show all results
    enhanced_search = false,
    system_prompt = ''
  ): Promise<{
    answer: string;
    sources?: SearchResult[];
    extracted_entities?: string[];
    llm_provider?: string;
    model?: string;
    web_search?: any;
    llm_knowledge?: any;
  }> => {
    try {
      const enableWebSearch = enhanced_search && ['gemini', 'claude', 'kimi', 'openrouter'].includes(llm_provider);
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
        system_prompt: system_prompt || null
      };
      console.log('🌐 API request body:', requestBody);

      // Use the new unified query endpoint
      const response = await fetch(`${GATEWAY_URL}/api/v1/query`, {
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

      // Transform the new API response to match the expected format
      // Handle different response structures based on mode
      if (mode === 'hybrid') {
        const entitiesResult = data.entities?.data?.result || '';
        const notesAnswer = data.notes?.data?.answer || '';
        const notesSources = data.notes?.data?.sources || [];

        // Flatten and format vector sources if available
        let vectorSources: SearchResult[] = [];
        const vectorData = data.vector?.data;
        if (vectorData && vectorData.documents && vectorData.documents[0]) {
          vectorSources = vectorData.documents[0].map((doc: string, i: number) => {
            const dist = vectorData.distances[0][i];
            // ChromaDB returns negative cosine distances (more negative = better match)
            // Typical range: -10 (excellent) to +2 (poor)
            // Use inverse exponential decay for better differentiation
            const relevance = dist !== undefined
              ? Math.max(0, Math.min(100, 100 / (1 + Math.exp(dist / 2))))
              : 50;

            return {
              filename: vectorData.metadatas[0][i]?.filename || 'unknown',
              filepath: vectorData.metadatas[0][i]?.filepath || 'unknown',
              relevance,
              snippet: doc.substring(0, 300) + '...'
            };
          });
        }

        const allSources = [...notesSources, ...vectorSources];
        const uniqueSources = allSources.filter((src, index, self) =>
          index === self.findIndex((t) => (
            t.filename === src.filename
          ))
        );

        let answer = notesAnswer || entitiesResult;
        if (!answer && vectorSources.length > 0) {
          answer = `Knowledge graph search was inconclusive, but found ${vectorSources.length} relevant snippets via vector search.`;
        } else if (!answer) {
          answer = 'No results found';
        }

        return {
          answer,
          sources: uniqueSources,
          extracted_entities: data.notes?.data?.extracted_entities || []
        };
      } else if (mode.includes('+') || mode === 'dual-graph') {
        // Dual-source modes: prefer entities (LightRAG) if available, otherwise notes (NetworkX)
        let answer = 'No results found';
        let sources = [];

        if (data.entities?.data) {
          answer = data.entities.data.result || data.entities.data.answer || answer;
        } else if (data.notes?.data) {
          answer = data.notes.data.answer || data.notes.data.result || answer;
        } else if (data.vector?.data) {
          const vectorData = data.vector.data;
          answer = vectorData.answer || vectorData.result || answer;
          sources = vectorData.sources || [];
        }

        // Collect sources from all available sources
        if (data.notes?.data?.sources) sources = data.notes.data.sources;
        if (data.vector?.data?.sources) sources = [...sources, ...data.vector.data.sources];

        return {
          answer,
          sources
        };
      } else if (mode === 'vector') {
        const vectorData = data.results || data;
        let sources: SearchResult[] = [];

        if (vectorData.documents && vectorData.documents[0]) {
          sources = vectorData.documents[0].map((doc: string, i: number) => {
            const dist = vectorData.distances[0][i];
            // ChromaDB returns negative cosine distances (more negative = better match)
            // Use inverse exponential decay for better differentiation
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
          answer: sources.length > 0 ? `Found ${sources.length} matching snippets in your vault.` : 'No results found',
          sources: sources
        };
      } else {
        // Other single-source modes (notes, entities)
        const result = data.results || data;
        return {
          answer: result.answer || result.result || 'No results found',
          sources: result.sources || []
        };
      }
    } catch (error) {
      console.error('Unified search error:', error);
      throw error;
    }
  },

  getStats: async () => {
    const gatewayData = await tryFetchJson(`${GATEWAY_URL}/api/v1/stats`);
    if (gatewayData) {
      return {
        documents: gatewayData.documents || 0,
        graph: gatewayData.graph || null
      };
    }

    const [embeddingData, graphData] = await Promise.all([
      tryFetchJson(`${EMBEDDING_URL}/stats`),
      tryFetchJson(`${GRAPH_URL}/stats`)
    ]);

    const documents = embeddingData?.total_documents || embeddingData?.documents || 0;
    const graph = graphData
      ? {
          nodes: graphData.total_nodes ?? graphData.nodes ?? 0,
          edges: graphData.total_edges ?? graphData.edges ?? 0,
          graph_loaded: true
        }
      : null;

    return { documents, graph };
  },

  getOllamaModels: async (): Promise<string[]> => {
    // This might still need to go direct if gateway doesn't proxy tags yet, 
    // BUT strictly we should use gateway. For now, assuming direct or proxied if available.
    // Keeping direct call for now as Gateway V1 might not have /tags proxy.
    // TODO: move to gateway /api/v1/models if implemented
    try {
      const response = await fetch('http://localhost:11434/api/tags');
      if (!response.ok) return [];

      const data = await response.json();
      const models = data.models || [];
      return models
        .filter((m: any) => !m.name.includes('embed'))
        .map((m: any) => m.name);
    } catch (error) {
      console.error('Failed to get Ollama models:', error);
      return [];
    }
  },

  submitFeedback: async (feedback: any): Promise<void> => {
    // Placeholder: feedback endpoint logic not yet in unified gateway V1 spec shown in context.
    // Leaving as no-op or direct call if service available.
    // Future: POST ${GATEWAY_URL}/api/v1/feedback
    console.log("Feedback not yet implemented in V1 Gateway", feedback);
  },

  checkApiKeys: async (): Promise<{ gemini: boolean; anthropic: boolean }> => {
    try {
      const response = await fetch('/api/check-api-keys');
      if (!response.ok) {
        return { gemini: false, anthropic: false };
      }
      return await response.json();
    } catch (error) {
      console.error('Failed to check API keys:', error);
      return { gemini: false, anthropic: false };
    }
  },

  // WebSocket URL for Deep Thinking
  deepResearchEndpoint: `${WS_GATEWAY_URL}/api/v1/deep-research`
};
