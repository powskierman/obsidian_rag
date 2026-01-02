const GATEWAY_URL = 'http://127.0.0.1:3000';
const WS_GATEWAY_URL = 'ws://127.0.0.1:3000';

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
    mode: 'vector' | 'notes' | 'entities' | 'notes+vector' | 'entities+vector' | 'dual-graph' | 'hybrid' = 'hybrid',
    n_results = 10,
    llm_provider = 'ollama',
    model = '',
    temperature = 0.7,
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
      // Use the new unified query endpoint
      const response = await fetch(`${GATEWAY_URL}/api/v1/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query,
          mode,
          max_results: n_results,
          llm_provider,
          model,
          temperature,
          system_prompt: system_prompt || null
        })
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
        // Hybrid mode returns { notes, entities, vector }
        // Prefer entities (LightRAG) result as it provides richer, synthesized content
        const entitiesResult = data.entities?.data?.result || '';
        const notesAnswer = data.notes?.data?.answer || '';

        return {
          answer: entitiesResult || notesAnswer || 'No results found',
          sources: data.notes?.data?.sources || [],
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
      } else {
        // Single-source modes
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
    try {
      const response = await fetch(`${GATEWAY_URL}/api/v1/stats`);
      if (!response.ok) return { documents: 0, graph: null };

      const data = await response.json();
      return {
        documents: data.documents || 0,
        graph: data.graph || null
      };
    } catch (error) {
      console.error('Stats error:', error);
      return { documents: 0, graph: null };
    }
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
