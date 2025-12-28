const EMBEDDING_URL = 'http://localhost:8000';
const GRAPH_URL = 'http://localhost:8002';

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
  vectorSearch: async (query: string, n_results = 10): Promise<SearchResult[]> => {
    try {
      const response = await fetch(`${EMBEDDING_URL}/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query,
          n_results,
          reranking: true,
          deduplicate: true
        })
      });

      if (!response.ok) throw new Error('Vector search failed');

      const data = await response.json();
      const { documents, metadatas, distances } = data;
      if (!documents?.[0]) return [];

      return documents[0].map((doc: string, idx: number) => ({
        filename: metadatas[0][idx]?.filename || 'unknown',
        filepath: metadatas[0][idx]?.filepath || '',
        relevance: 100 - (distances[0][idx] * 100), // Simple conversion
        snippet: doc
      }));
    } catch (error) {
      console.error('Vector search error:', error);
      return [];
    }
  },

  graphQuery: async (
    query: string,
    mode: 'vector' | 'graph' | 'hybrid' = 'graph',
    n_results = 10,
    llm_provider = 'ollama',
    model = '',
    temperature = 0.7,
    system_prompt = '',
    web_search = false,
    llm_knowledge = false
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
      const response = await fetch(`${GRAPH_URL}/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query,
          mode,
          max_entities: 20,
          n_results,
          llm_provider,
          model,
          temperature,
          system_prompt,
          web_search,
          llm_knowledge
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Graph query failed:', response.status, errorText);
        throw new Error(`Graph query failed: ${response.status} ${errorText}`);
      }

      const data = await response.json();

      // Handle responses with sources (vector or hybrid mode)
      if (data.sources) {
        return {
          answer: data.answer,
          sources: data.sources,
          extracted_entities: data.extracted_entities,
          llm_provider: data.llm_provider,
          model: data.model,
          web_search: data.web_search,
          llm_knowledge: data.llm_knowledge
        };
      }

      // Handle graph-only mode
      return {
        answer: data.answer,
        web_search: data.web_search,
        llm_knowledge: data.llm_knowledge
      };
    } catch (error) {
      console.error('Graph query error:', error);
      throw error;
    }
  },

  getStats: async () => {
    try {
      const [embedResponse, graphResponse] = await Promise.all([
        fetch(`${EMBEDDING_URL}/stats`).catch(() => null),
        fetch(`${GRAPH_URL}/health`).catch(() => null)
      ]);

      const embedData = embedResponse?.ok ? await embedResponse.json() : null;
      console.log('API Stats Debug:', embedData); // Debug log in browser console

      const graphData = graphResponse?.ok ? await graphResponse.json() : null;

      // Robust check for different response structures
      const totalDocs = embedData?.total_documents
        ?? embedData?.count
        ?? embedData?.stats?.total_documents
        ?? 0;

      return {
        documents: totalDocs,
        graph: graphData
      };
    } catch (error) {
      console.error('Stats error:', error);
      return { documents: 0, graph: null };
    }
  },

  getOllamaModels: async (): Promise<string[]> => {
    try {
      const response = await fetch('http://localhost:11434/api/tags');
      if (!response.ok) return [];

      const data = await response.json();
      // Filter out embedding-only models
      const models = data.models || [];
      return models
        .filter((m: any) => !m.name.includes('embed'))
        .map((m: any) => m.name);
    } catch (error) {
      console.error('Failed to get Ollama models:', error);
      return [];
    }
  },

  submitFeedback: async (feedback: {
    query_id: string;
    rating: number;
    query: string;
    search_mode: string;
    model: string;
    timestamp: string;
  }): Promise<void> => {
    try {
      const response = await fetch(`${EMBEDDING_URL}/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(feedback)
      });

      if (!response.ok) {
        console.error('Failed to submit feedback');
      }
    } catch (error) {
      console.error('Feedback submission error:', error);
    }
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
  }
};
