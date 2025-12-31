const GATEWAY_URL = 'http://127.0.0.1:4000';
const WS_GATEWAY_URL = 'ws://127.0.0.1:4000';

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
    mode: 'vector' | 'graph' | 'hybrid' = 'vector',
    n_results = 10,
    llm_provider = 'ollama',
    model = '',
    temperature = 0.7,
    enhanced_search = false
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
      const response = await fetch(`${GATEWAY_URL}/api/v1/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query,
          mode,
          n_results,
          llm_provider,
          model,
          temperature,
          enhanced_search
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Unified search failed:', response.status, errorText);
        throw new Error(`Unified search failed: ${response.status} ${errorText}`);
      }

      return await response.json();
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
