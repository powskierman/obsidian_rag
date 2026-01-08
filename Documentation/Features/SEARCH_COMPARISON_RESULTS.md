# Search Mode Comparison

| Mode | Best For | Dependencies | Notes |
| --- | --- | --- | --- |
| vector | fast retrieval, exact topic lookup | embedding service | no graph required |
| graph | relationship reasoning | graph service + LLM | slower, better for connections |
| hybrid | general use | graph + embedding | balanced answer + sources |
| dual-graph | combined NetworkX + LightRAG | API gateway + both graphs | returns separate graph outputs |
| cascading | targeted research with progressive expansion | graph + LightRAG + embedding | anchors → entities → expansion → vector |

## Guidance

- Start with **vector** for recall and speed.
- Use **graph** for “how are these related” questions.
- Use **hybrid** for most queries that need sources.
- Use **dual-graph** when you want both note-graph and entity-graph perspectives.
