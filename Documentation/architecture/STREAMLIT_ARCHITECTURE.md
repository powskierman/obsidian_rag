# Streamlit Architecture

Streamlit UI talks to the API gateway, which routes to vector, graph, and LightRAG services.

Flow:

```
Streamlit UI -> API Gateway -> (Embedding, Graph, LightRAG)
```

The UI does not perform retrieval logic; it sends requests to the gateway.
