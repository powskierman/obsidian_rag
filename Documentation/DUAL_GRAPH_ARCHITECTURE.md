# Dual Graph Architecture

The system uses two complementary graphs plus a vector store:

- **LightRAG (port 8001)**: entity-centric semantic graph.
- **NetworkX (port 8002)**: note-centric link graph.
- **ChromaDB (port 8000)**: vector similarity search.

## When to Use Which

- **LightRAG**: concept discovery and multi-hop semantic queries.
- **NetworkX**: explicit note linkage, navigation, and structure questions.
- **Vector**: fast, direct similarity lookup.

## Related Docs

- `Documentation/DUAL_GRAPH_QUERY_API.md`
- `Documentation/Graph/IMPROVED_GRAPH_BUILDER_GUIDE.md`
- `Documentation/Embedding/EMBEDDING_MODEL_INFO.md`
