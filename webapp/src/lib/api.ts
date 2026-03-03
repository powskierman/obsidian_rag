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

const GATEWAY_URL = resolveUrl(process.env.NEXT_PUBLIC_GATEWAY_URL, '4000');
const WS_GATEWAY_URL = resolveUrl(process.env.NEXT_PUBLIC_WS_GATEWAY_URL, '4000', true);
const EMBEDDING_URL = resolveUrl(process.env.NEXT_PUBLIC_EMBEDDING_URL, '8000');
const GRAPH_URL = resolveUrl(process.env.NEXT_PUBLIC_GRAPH_URL, '8002');

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
  sourceType?: 'linked-note' | 'direct-excerpt' | 'entity-context';
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
  };
};

const normalizeVectorSources = (
  vectorData: any,
  sourceType: SearchResult['sourceType'] = 'direct-excerpt'
): SearchResult[] => {
  if (!vectorData) return [];

  if (Array.isArray(vectorData.sources) && vectorData.sources.length > 0) {
    return vectorData.sources.map((source: any) => {
      const normalized = normalizeSource(source);
      return {
        ...normalized,
        sourceType: normalized.sourceType || sourceType,
      };
    });
  }

  if (vectorData.documents && vectorData.documents[0]) {
    return vectorData.documents[0].map((doc: string, i: number) => {
      const dist = vectorData.distances?.[0]?.[i];
      const relevance = dist !== undefined
        ? Math.max(0, Math.min(100, 100 / (1 + Math.exp(Number(dist) / 2))))
        : 50;

      return {
        filename: vectorData.metadatas?.[0]?.[i]?.filename || 'unknown',
        filepath: vectorData.metadatas?.[0]?.[i]?.filepath || 'unknown',
        relevance,
        snippet: doc,
        sourceType,
      };
    });
  }

  return [];
};

const normalizeTaggedSources = (
  sources: any[],
  sourceType: SearchResult['sourceType']
): SearchResult[] => {
  if (!Array.isArray(sources)) return [];
  return sources.map((source: any) => {
    const normalized = normalizeSource(source);
    return {
      ...normalized,
      sourceType: normalized.sourceType || sourceType,
    };
  });
};

const isInsufficientAnswer = (answer: string | undefined): boolean => {
  if (!answer || !answer.trim()) return true;
  const cleaned = answer.trim().toLowerCase();
  return [
    'cannot provide the analysis',
    'cannot answer',
    'insufficient information',
    'no relevant notes',
    'no relevant relationships',
    'no relevant notes or relationships',
    'provided knowledge graph',
    'would need:',
    'i would need',
    'placeholder',
    '[unknown]',
    'without properly labeled notes',
    'if you can provide a clearer knowledge graph',
  ].some((pattern) => cleaned.includes(pattern));
};

const buildCombinedAnswer = (
  mode: string,
  noteSources: SearchResult[],
  entitySources: SearchResult[],
  vectorSources: SearchResult[]
): string => {
  if (mode === 'notes+vector') {
    if (noteSources.length > 0 && vectorSources.length > 0) {
      return `Showing ${noteSources.length} linked-note context items and ${vectorSources.length} direct note excerpts below.`;
    }
    if (noteSources.length > 0) {
      return `Showing ${noteSources.length} linked-note context items below.`;
    }
    if (vectorSources.length > 0) {
      return `Showing ${vectorSources.length} direct note excerpts below.`;
    }
  }

  if (mode === 'entities+vector') {
    if (entitySources.length > 0 && vectorSources.length > 0) {
      return `Showing ${entitySources.length} entity-context items and ${vectorSources.length} direct note excerpts below.`;
    }
    if (entitySources.length > 0) {
      return `Showing ${entitySources.length} entity-context items below.`;
    }
    if (vectorSources.length > 0) {
      return `Showing ${vectorSources.length} direct note excerpts below.`;
    }
  }

  if (mode === 'dual-graph') {
    if (noteSources.length > 0 && entitySources.length > 0) {
      return `Showing ${noteSources.length} linked-note context items and ${entitySources.length} entity-context items below.`;
    }
  }

  return 'No results found';
};

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
    retrievalIntent?: string;
    llm_provider?: string;
    model?: string;
    web_search?: any;
    llm_knowledge?: any;
  }> => {
    try {
      const enableWebSearch = enhanced_search && ['gemini', 'claude', 'kimi', 'openrouter', 'chatgpt'].includes(llm_provider);
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
        const noteSources = normalizeTaggedSources(data.notes?.data?.sources || [], 'linked-note');
        const entitySources = normalizeTaggedSources(data.entities?.data?.sources || [], 'entity-context');
        const vectorSources = normalizeVectorSources(data.vector?.data, 'direct-excerpt');
        const topLevelSources = Array.isArray(data.sources)
          ? data.sources.map((source: any) => normalizeSource(source))
          : [];

        let sources = topLevelSources.length > 0
          ? topLevelSources
          : [...noteSources, ...entitySources, ...vectorSources];

        let answer = data.answer
          || data.entities?.data?.result
          || data.entities?.data?.answer
          || data.notes?.data?.answer
          || data.notes?.data?.result
          || data.vector?.data?.answer
          || data.vector?.data?.result
          || 'No results found';

        if (isInsufficientAnswer(answer) && sources.length > 0) {
          answer = buildCombinedAnswer(mode, noteSources, entitySources, vectorSources);
        }

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
      } else if (mode === 'cascading') {
        return {
          answer: data.answer || 'No results found',
          sources: (data.sources || []).map(normalizeSource),
          extracted_entities: data.results?.entities || [],
          retrievalIntent: data.retrieval_intent || data.results?.retrieval_intent
        };
      } else {
        // Other single-source modes (notes, entities)
        const result = data.results || data;
        const topSources = Array.isArray(data.sources) ? data.sources : [];
        const nestedSources = Array.isArray(result.sources) ? result.sources : [];
        let sources: SearchResult[] = (topSources.length > 0 ? topSources : nestedSources).map(normalizeSource);
        let answer = data.answer || result.answer || result.result || data.result || 'No results found';

        // Handle vector-fallback payloads returned under `results` for entities mode.
        if ((!sources || sources.length === 0) && result.documents && result.documents[0]) {
          sources = result.documents[0].map((doc: string, i: number) => {
            const dist = result.distances?.[0]?.[i];
            const relevance = dist !== undefined
              ? Math.max(0, Math.min(100, 100 / (1 + Math.exp(dist / 2))))
              : 50;
            return {
              filename: result.metadatas?.[0]?.[i]?.filename || 'unknown',
              filepath: result.metadatas?.[0]?.[i]?.filepath || 'unknown',
              relevance,
              snippet: doc
            };
          });
          answer = `Found ${sources.length} matching snippets in your vault.`;
        }

        return {
          answer,
          sources,
          retrievalIntent: data.retrieval_intent || result.retrieval_intent
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
        graph: gatewayData.graph || null,
        lightrag: gatewayData.lightrag || null
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

    return { documents, graph, lightrag: null };
  },

  getOllamaModels: async (): Promise<string[]> => {
    // This might still need to go direct if gateway doesn't proxy tags yet, 
    // BUT strictly we should use gateway. For now, assuming direct or proxied if available.
    // Keeping direct call for now as Gateway V1 might not have /tags proxy.
    // TODO: move to gateway /api/v1/models if implemented
    try {
      const OLLAMA_URL = process.env.NEXT_PUBLIC_OLLAMA_URL || 'http://localhost:11434';
      const response = await fetch(`${OLLAMA_URL}/api/tags`);
      if (!response.ok) return [];

      const data = await response.json();
      const models = data.models || [];
      return models
        .filter((m: any) => !m.name.includes('embed'))
        .map((m: any) => m.name);
    } catch (error) {
      // Avoid using console.error(error) to prevent Next.js from throwing dev overlays
      console.log('Ollama is not running locally or unreachable. Returning empty model list.');
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

  getEnvConfig: async (): Promise<{ keys: { gemini: boolean; anthropic: boolean; openai: boolean; mlx: boolean }; models: Record<string, string> }> => {
    try {
      const response = await fetch('/api/env-config');
      if (!response.ok) {
        return {
          keys: { gemini: false, anthropic: false, openai: false, mlx: false },
          models: {}
        };
      }
      return await response.json();
    } catch (error) {
      console.error('Failed to get env config:', error);
      return {
        keys: { gemini: false, anthropic: false, openai: false, mlx: false },
        models: {}
      };
    }
  },

  // WebSocket URL for Deep Thinking
  deepResearchEndpoint: `${WS_GATEWAY_URL}/api/v1/deep-research`
};
