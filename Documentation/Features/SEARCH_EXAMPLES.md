# Knowledge Graph Search Examples

This guide provides practical examples for querying your knowledge graph using different methods.

## Quick Reference

- **CLI**: `python build_knowledge_graph.py` → Option 5
- **Web UI**: http://localhost:8501 (after `docker-compose up -d`)
- **MCP**: Ask Claude Desktop/Cursor directly
- **API**: `curl` or HTTP client to `http://localhost:8002`

---

## Method 1: CLI Interactive Query

### Start Interactive Mode

```bash
python build_knowledge_graph.py
# Choose Option 5: Interactive query mode
# Graph file: graph_data/knowledge_graph_full.pkl (or press Enter)
```

### Example Queries

**Entity Exploration:**
```
entity Home Assistant
entity CAR-T Therapy
entity ESP32
```

**Relationship Queries:**
```
path ESP32 to Home Assistant
path CAR-T to lymphoma
path Swift to iOS
```

**General Questions:**
```
What treatments are mentioned in my notes?
How does ESP32 relate to Home Assistant?
What medical conditions are discussed?
What technologies do I use for home automation?
```

**Statistics:**
```
stats
```

**Exit:**
```
quit
```

---

## Method 2: Web UI (Streamlit)

### Start the UI

```bash
docker-compose up -d
# Open http://localhost:8501
```

### Search Modes and LLM Providers

The UI offers two independent selections:

**🔍 Search Mode:**
- **`vector`**: Fast semantic search using ChromaDB embeddings
- **`graph-claude`**: Knowledge graph search using Claude's reasoning

**🤖 LLM Provider:**
- **Ollama (Free)**: Local models for answer generation
- **Claude API ($)**: High-quality paid API for answer generation

**How They Work Together:**

| Search Mode | LLM Provider | How It Works |
|------------|--------------|--------------|
| **vector** | **Ollama** | ✅ ChromaDB retrieval → Ollama generates answer |
| **vector** | **Claude** | ✅ ChromaDB retrieval → Claude generates answer |
| **graph-claude** | *Any* | ⚠️ Graph service uses Claude internally (answer already synthesized) |

**Important Notes:**
- **Vector search** can use either Ollama or Claude for answer generation
- **Graph-claude** always uses Claude internally (the graph service hardcodes Claude)
- When using `graph-claude`, the LLM Provider selection is ignored because the answer is already synthesized by Claude in the graph service

**Future Enhancement:**
A `graph-ollama` mode could be added to allow graph search with Ollama, but this would require modifying the graph service to support alternative LLMs.

### Example Queries

**Medical/Health:**
- "What cancer treatments are mentioned?"
- "What are the side effects of CAR-T therapy?"
- "What medical conditions are discussed?"

**Technology:**
- "What home automation technologies are used?"
- "How does ESP32 integrate with Home Assistant?"
- "What programming languages are mentioned?"

**Projects:**
- "What projects involve 3D printing?"
- "What Swift development projects are mentioned?"
- "What hardware projects use ESP32?"

**Relationships:**
- "How does X relate to Y?"
- "What connects treatment A to condition B?"

---

## Method 3: MCP (Claude Desktop/Cursor)

### Setup

Configure `knowledge_graph_mcp.py` in your MCP settings, then ask Claude directly:

### Example Queries

**Direct Questions:**
```
Query my knowledge graph: What treatments are mentioned for lymphoma?
Get entity info for Home Assistant
Find paths between ESP32 and Raspberry Pi
Search entities: CAR-T
Get graph stats
```

**Natural Language:**
```
What do I know about CAR-T therapy?
How is ESP32 used in my projects?
What medical information is in my notes?
What technologies connect to Home Assistant?
```

---

## Method 4: REST API

### Health Check

```bash
curl http://localhost:8002/health
```

### Query the Graph

```bash
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What treatments are mentioned?",
    "max_entities": 20
  }'
```

### Get Entity Info

```bash
curl http://localhost:8002/entity/Home%20Assistant
```

### Find Paths

```bash
curl -X POST http://localhost:8002/path \
  -H "Content-Type: application/json" \
  -d '{
    "source": "ESP32",
    "target": "Home Assistant",
    "max_depth": 3
  }'
```

### Search Entities

```bash
curl -X POST http://localhost:8002/search_entities \
  -H "Content-Type: application/json" \
  -d '{
    "search_term": "treatment",
    "limit": 10
  }'
```

### Get Statistics

```bash
curl http://localhost:8002/stats
```

---

## Example Query Patterns

### Medical/Health Queries

**Treatments:**
```
"What cancer treatments are mentioned?"
"What treatments are available for lymphoma?"
"What medications are discussed?"
```

**Conditions:**
```
"What medical conditions are in my notes?"
"What symptoms are mentioned?"
"What diagnoses are discussed?"
```

**Relationships:**
```
"How does CAR-T therapy relate to lymphoma?"
"What treatments are used for specific conditions?"
```

### Technology Queries

**Hardware:**
```
"What hardware projects use ESP32?"
"How does ESP32 connect to other devices?"
"What microcontrollers are mentioned?"
```

**Software:**
```
"What programming languages are used?"
"What frameworks are mentioned?"
"What development tools are discussed?"
```

**Integration:**
```
"How does Home Assistant integrate with ESP32?"
"What technologies work together?"
```

### Project Queries

**By Topic:**
```
"What projects involve 3D printing?"
"What home automation projects are mentioned?"
"What medical research projects are discussed?"
```

**By Technology:**
```
"What projects use Swift?"
"What projects use ESP32?"
"What projects involve Home Assistant?"
```

### Relationship Queries

**Direct Connections:**
```
"path ESP32 to Home Assistant"
"path CAR-T to lymphoma"
"path Swift to iOS"
```

**Multi-hop:**
```
"How does X connect to Y through Z?"
"What is the relationship chain between A and B?"
```

**Exploration:**
```
"What is connected to Home Assistant?"
"What does ESP32 relate to?"
"What entities connect to CAR-T therapy?"
```

---

## Advanced Query Examples

### Finding Related Concepts

**CLI:**
```
entity Home Assistant
# Then explore the relationships shown
```

**Natural Language:**
```
"What concepts are related to home automation?"
"What technologies are used together?"
"What medical concepts are connected?"
```

### Exploring Entity Neighborhoods

**MCP:**
```
Get entity info for Home Assistant
# Shows all incoming and outgoing relationships
```

**API:**
```bash
curl http://localhost:8002/entity/Home%20Assistant
```

### Finding Common Connections

**Question Pattern:**
```
"What do X and Y have in common?"
"What connects treatment A and treatment B?"
```

**Path Query:**
```
path TreatmentA to TreatmentB
# Shows the connection path
```

### Discovering New Connections

**Exploratory:**
```
"What entities are most connected?"
"What are the top relationships?"
"Show me entities with many connections"
```

---

## Query Tips

### 1. Be Specific
- ✅ Good: "What treatments are mentioned for lymphoma?"
- ❌ Vague: "What is mentioned?"

### 2. Use Entity Names
- ✅ Good: "entity Home Assistant"
- ❌ Less effective: "home assistant stuff"

### 3. Explore Relationships
- Start with an entity you know
- Follow the relationships to discover new connections
- Use path queries to understand connections

### 4. Combine Methods
- Use CLI for quick exploration
- Use Web UI for visual exploration
- Use MCP for natural language queries
- Use API for programmatic access

### 5. Iterative Exploration
```
1. Start with a general query: "What treatments are mentioned?"
2. Find interesting entities: "CAR-T Therapy"
3. Explore relationships: "entity CAR-T Therapy"
4. Follow connections: "path CAR-T to lymphoma"
5. Discover new entities: "What else relates to lymphoma?"
```

---

## Common Use Cases

### Medical Research

```bash
# Find all treatments
Query: "What treatments are mentioned?"

# Explore a specific treatment
Query: "entity CAR-T Therapy"

# Find treatment relationships
Query: "path CAR-T to lymphoma"

# Find related conditions
Query: "What conditions relate to lymphoma?"
```

### Technology Projects

```bash
# Find hardware projects
Query: "What projects use ESP32?"

# Explore integration
Query: "path ESP32 to Home Assistant"

# Find related technologies
Query: "What technologies work with Home Assistant?"
```

### Knowledge Discovery

```bash
# Find highly connected entities
Query: "stats"  # Shows top connected entities

# Explore from a known entity
Query: "entity Home Assistant"

# Discover new connections
Query: "What entities connect to ESP32?"
```

---

## Troubleshooting Queries

### No Results Found

**Try:**
- Use more general terms
- Check entity name spelling (case-sensitive)
- Use partial matches: "search_entities" with partial term
- Explore related entities first

### Too Many Results

**Try:**
- Be more specific in your query
- Use entity filters
- Limit results with `limit` parameter
- Focus on specific relationship types

### Entity Not Found

**Try:**
- Check exact spelling (case matters)
- Use search_entities to find similar names
- Check if entity exists with stats command
- Try partial name search

---

## Example Session

```
$ python build_knowledge_graph.py
# Choose Option 5

> stats
📊 Graph Statistics:
   Nodes: 35,048
   Edges: 80,200
   Top entities: Home Assistant (329 connections), ESP32 (284 connections)...

> entity Home Assistant
📍 Entity: Home Assistant
Type: technology
Connections: 329
Outgoing: uses → ESP32, integrates → MQTT, ...
Incoming: used_in → Home Automation Project, ...

> path ESP32 to Home Assistant
🛤️ Found 2 paths:
1. ESP32 → uses → MQTT → connects_to → Home Assistant
2. ESP32 → communicates_with → Home Assistant

> "What home automation technologies are mentioned?"
💬 Answer: Based on your knowledge graph, you have extensive 
home automation setup including:
- Home Assistant (329 connections)
- ESP32 microcontrollers (284 connections)
- MQTT protocol
- Various sensors and actuators
...

> quit
```

---

## API Response Examples

### Query Response

```json
{
  "answer": "Based on your knowledge graph...",
  "entities_considered": 20,
  "sources": [...]
}
```

### Entity Info Response

```json
{
  "entity": "Home Assistant",
  "type": "technology",
  "properties": {...},
  "outgoing": [
    {"relationship": "uses", "target": "ESP32"},
    ...
  ],
  "incoming": [
    {"relationship": "used_in", "source": "Home Automation Project"},
    ...
  ]
}
```

### Path Response

```json
{
  "paths": [
    ["ESP32", "MQTT", "Home Assistant"],
    ["ESP32", "Home Assistant"]
  ],
  "count": 2
}
```

---

## Best Practices

1. **Start Broad, Then Narrow**: Begin with general queries, then explore specific entities
2. **Use Multiple Methods**: CLI for quick checks, Web UI for exploration, MCP for natural language
3. **Follow Relationships**: Use path queries to understand connections
4. **Check Statistics**: Use `stats` to find highly connected entities
5. **Iterate**: Use query results to inform next queries

---

## Quick Command Reference

### CLI Commands
- `stats` - Graph statistics
- `entity <name>` - Entity details
- `path <source> to <target>` - Find paths
- `"<question>"` - Natural language query
- `quit` - Exit

### API Endpoints
- `GET /health` - Health check
- `POST /query` - Query graph
- `GET /entity/<name>` - Entity info
- `POST /path` - Find paths
- `POST /search_entities` - Search entities
- `GET /stats` - Statistics

### MCP Tools
- `query_knowledge_graph` - Ask questions
- `get_entity_info` - Entity details
- `find_entity_path` - Find paths
- `search_entities` - Search entities
- `get_graph_stats` - Statistics

