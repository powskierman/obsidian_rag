# Knowledge Graph Test Prompts

## Primary Test Prompt

Use this prompt to test the knowledge graph's relationship understanding:

```
Use obsidian_graph_query to answer: What treatments are mentioned for lymphoma and how do they relate to each other?
```

## Additional Test Prompts

### 1. Treatment Relationships
```
Use obsidian_graph_query to explain: How does CAR-T therapy relate to lymphoma and what other treatments connect to it?
```

### 2. Entity Exploration
```
Use get_entity_info to explore: CAR-T Therapy
```

### 3. Find Connection Paths
```
Use find_entity_path to find connections between: CAR-T Therapy and Lymphoma
```

### 4. Search for Entities
```
Use search_entities to find entities related to: treatment
```

### 5. Graph Statistics
```
Use get_graph_stats to see overall graph statistics
```

### 6. Comprehensive Treatment Analysis
```
Use obsidian_graph_query to analyze: What are all the lymphoma treatment options mentioned in my notes, their side effects, and how they compare to each other?
```

### 7. Treatment Timeline
```
Use obsidian_graph_query to understand: What is the sequence of treatments I've had and how do they relate to my lymphoma diagnosis?
```

## Expected Results Format

After running a test, document:

1. **Query:** The exact prompt used
2. **Tool:** Which tool was called
3. **Response:** The answer provided
4. **Entities Found:** List of entities identified
5. **Relationships:** Connections discovered
6. **Quality:** How well it answered the question
7. **Comparison:** How it differs from semantic search results

## Testing Workflow

1. **Run the primary test prompt** in Claude Desktop
2. **Copy the results** 
3. **Add to SEARCH_COMPARISON_RESULTS.md** in the Knowledge Graph section
4. **Compare** with semantic search results for the same topic
5. **Document insights** about when to use each method

