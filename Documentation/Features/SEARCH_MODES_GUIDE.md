# Search Mode Comparison

| Mode | Best For | Dependencies | Notes |
| --- | --- | --- | --- |
| vector | fast retrieval, exact topic lookup | embedding service | no graph required |
| notes | relationship reasoning over wiki links | graph service + LLM | canonical replacement for legacy `graph` |
| entities | entity-centric reasoning | LightRAG service | semantic entity graph |
| hybrid | general use | graph + embedding | balanced answer + sources |
| dual-graph | combined NetworkX + LightRAG | API gateway + both graphs | returns separate graph outputs |
| cascading | targeted research with progressive expansion | graph + LightRAG + embedding | anchors → entities → expansion → vector |

## Guidance

- Start with **vector** for recall and speed.
- Use **notes** for “how are these notes related” questions.
- Use **entities** for entity/relationship-oriented questions.
- Use **hybrid** for most queries that need sources.
- Use **dual-graph** when you want both note-graph and entity-graph perspectives.
