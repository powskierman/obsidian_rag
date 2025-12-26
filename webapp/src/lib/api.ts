const EMBEDDING_URL = 'http://localhost:8000';
const GRAPH_URL = 'http://localhost:8002';

export interface SearchResult {
  content: string;
  metadata: any;
  score: number;
}

export interface GraphEntity {
  name: string;
  type: string;
  connections: number;
  sources?: { filename: string; chunk_id: string }[];
}

export const api = {
  // Embedding Service (Vector Search)
  async vectorSearch(query: string, nResults: number = 5): Promise<any> {
    const res = await fetch(`${EMBEDDING_URL}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        n_results: nResults,
        reranking: true,
        deduplicate: true
      }),
    });
    if (!res.ok) throw new Error('Vector search failed');
    return res.json();
  },

  // Graph Service (Relationship Search)
  async graphQuery(query: string, maxEntities: number = 20, mode: string = 'hybrid', webSearch: boolean = false, model: string = 'moonshotai/kimi-k2-0905', sources: number = 10, temperature: number = 0.3, showSources: boolean = true, enhancedSearch: boolean = false) {
    const res = await fetch(`${GRAPH_URL}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        max_entities: maxEntities,
        mode,
        web_search: webSearch,
        model,
        sources,
        temperature,
        show_sources: showSources,
        enhanced_search: enhancedSearch
      }),
    });
    if (!res.ok) throw new Error('Graph query failed');
    return res.json();
  },

  async searchEntities(query: string, limit: number = 10): Promise<{ results: GraphEntity[] }> {
    const res = await fetch(`${GRAPH_URL}/search_entities`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit }),
    });
    if (!res.ok) throw new Error('Entity search failed');
    return res.json();
  },

  async getGraphStats() {
    try {
      const res = await fetch(`${GRAPH_URL}/stats`);
      if (!res.ok) return { nodes: 0, edges: 0 };
      const data = await res.json();
      return {
        nodes: data.nodes || data.total_nodes || 0,
        edges: data.edges || data.total_edges || 0
      };
    } catch (e) {
      return { nodes: 0, edges: 0 };
    }
  },

  async getNoteContent(filename: string): Promise<{ filename: string; content: string }> {
    const res = await fetch(`${GRAPH_URL}/get_note_content`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename }),
    });
    if (!res.ok) throw new Error('Failed to fetch note content');
    return res.json();
  },

  // Service Health
  async getVectorStats(): Promise<{ chunks: number }> {
    try {
      const res = await fetch(`${EMBEDDING_URL}/stats`);
      if (!res.ok) return { chunks: 0 };
      const data = await res.json();
      return { chunks: data.total_documents || data.stats?.total_chunks || 0 };
    } catch (e) {
      return { chunks: 0 };
    }
  },

  async getOllamaModels(): Promise<{ count: number, models: string[] }> {
    try {
      // We can't hit Ollama directly from browser due to CORS usually, unless configured.
      // But we can try hitting localhost:11434/api/tags
      const res = await fetch('http://localhost:11434/api/tags');
      if (!res.ok) return { count: 0, models: [] };
      const data = await res.json();
      return { count: data.models?.length || 0, models: data.models?.map((m: any) => m.name) || [] };
    } catch (e) {
      return { count: 0, models: [] };
    }
  }
};
