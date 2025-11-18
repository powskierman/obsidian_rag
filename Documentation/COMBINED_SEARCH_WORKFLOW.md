# Combined Search Workflow: Graph + Semantic Search

## Overview

Use both knowledge graph and semantic search together for comprehensive understanding:
1. **Graph** → Discover entities and their prominence
2. **Semantic Search** → Get detailed context and relationships
3. **Combine** → Full picture of both structure and content

## Prompt Templates

### Template 1: Step-by-Step Explicit

```
First, use obsidian_graph_query to discover: What treatments are mentioned for lymphoma?

Then, based on the entities you find, use obsidian_semantic_search to get detailed information about how those treatments relate to each other.

Finally, combine the insights: entity discovery from the graph with detailed context from semantic search.
```

### Template 2: Single Comprehensive Prompt

```
Use a two-step approach to understand lymphoma treatments:

1. Start with obsidian_graph_query to identify what treatment entities exist in my knowledge graph
2. Then use obsidian_semantic_search to find detailed information about how those treatments relate to each other, including sequences, comparisons, and side effects

Combine both results to give me a comprehensive overview.
```

### Template 3: Natural Language (Claude Figures It Out)

```
I want to understand all the lymphoma treatments mentioned in my notes and how they relate to each other. Use both my knowledge graph and semantic search to give me a complete picture.
```

### Template 4: Specific Entity Focus

```
First, use obsidian_graph_query to find what treatments are mentioned for lymphoma.

Then, for each treatment you discover (like CAR-T or chemotherapy), use obsidian_semantic_search to find detailed information about:
- How they relate to each other
- Treatment sequences
- Side effects and comparisons

Give me a comprehensive analysis combining entity discovery with detailed context.
```

## Example Prompts for Different Use Cases

### Medical Treatment Research

```
Use obsidian_graph_query to discover: What cancer treatments are mentioned in my notes?

Then use obsidian_semantic_search to find detailed information about:
- Treatment sequences and timing
- Side effect comparisons
- Efficacy information
- How treatments relate to my specific condition

Combine both to give me a complete treatment overview.
```

### Technology Project Exploration

```
First, use obsidian_graph_query to identify: What home automation technologies are in my knowledge graph?

Then use obsidian_semantic_search to find:
- How these technologies integrate
- Project details and implementations
- Technical specifications

Combine entity discovery with detailed project information.
```

### Entity Relationship Analysis

```
1. Use obsidian_graph_query: What entities relate to CAR-T therapy?
2. Use obsidian_semantic_search: How does CAR-T relate to lymphoma and other treatments?
3. Combine: Show me both the graph structure and detailed narrative context.
```

## Advanced: Multi-Step Workflow

### Comprehensive Medical Query

```
I want a complete analysis of my lymphoma treatment information. Please:

Step 1: Use obsidian_graph_query to discover all treatment entities mentioned
Step 2: Use get_entity_info for CAR-T Therapy to see its graph connections
Step 3: Use obsidian_semantic_search to find detailed treatment information and relationships
Step 4: Use find_entity_path to see how CAR-T connects to Lymphoma in the graph
Step 5: Combine all insights into a comprehensive treatment overview

Include:
- What treatments exist (from graph)
- How prominent each is (relationship counts)
- Detailed context about each (from semantic search)
- How they relate (from both graph and search)
```

## Quick Reference Prompts

### Discovery + Details
```
Use obsidian_graph_query to discover entities related to [topic], then use obsidian_semantic_search to get detailed information about them.
```

### Entity + Context
```
First find what [entities] exist using obsidian_graph_query, then use obsidian_semantic_search to understand the detailed context and relationships.
```

### Graph Structure + Content
```
Use obsidian_graph_query to see the structure of [topic] in my knowledge graph, then use obsidian_semantic_search to get the actual content and details.
```

## Tips for Effective Prompts

### ✅ Good Prompts

- **Explicit about tools**: "Use obsidian_graph_query first, then obsidian_semantic_search"
- **Clear purpose**: "Discover entities, then get details"
- **Combined output**: "Combine both results"
- **Specific goals**: "Find treatments, then their relationships"

### ❌ Less Effective

- Vague: "Search my vault" (Claude might pick one method)
- No combination: "Use graph query" (doesn't get details)
- Unclear sequence: "Search and query" (order matters)

## Real-World Success Example

### The Prompt

```
First, use obsidian_graph_query to discover: What treatments are mentioned for lymphoma?

Then, use obsidian_semantic_search to find detailed information about how those treatments relate to each other.

Combine both results to give me a comprehensive overview.
```

### The Result

Claude provided a **comprehensive treatment overview** that included:

**From Knowledge Graph:**
- Treatment entities (CAR-T, ASCT, Chemotherapy)
- Treatment structure and prominence

**From Semantic Search:**
- Treatment sequencing (CAR-T vs ASCT with clinical trial data)
- Treatment roles (lymphodepleting chemo as CAR-T preparation)
- Backup options (bispecific antibodies)
- Complementary approaches (BCL2 inhibitors, ADCs)
- Personal context (Yescarta journey, monitoring)

**Combined Synthesis:**
- Primary treatment pathways
- Treatment hierarchies and sequences
- Clinical data (EFS, OS comparisons)
- Practical considerations
- Personal journey integration

### Why This Worked

1. ✅ **Explicit sequence**: "First graph, then search"
2. ✅ **Clear combination**: "Combine both results"
3. ✅ **Specific goal**: "Comprehensive overview"
4. ✅ **Both tools used**: Graph for structure, search for context

### Key Takeaway

This example shows the **power of the combined approach** - neither tool alone could provide this level of comprehensive, contextual, and actionable information.

## Example: Complete Workflow

**User Prompt:**
```
I want to understand my lymphoma treatment options. Use both my knowledge graph and semantic search to give me:
1. What treatments exist (from graph)
2. How they relate to each other (from semantic search)
3. Detailed information about each (from semantic search)
```

**Claude's Process:**
1. Calls `obsidian_graph_query`: "What treatments are mentioned for lymphoma?"
   - Discovers: CAR-T (9 relationships), Chemotherapy
   
2. Calls `obsidian_semantic_search`: "CAR-T therapy and chemotherapy relationship"
   - Gets: 10 documents with detailed context
   
3. Combines results:
   - Graph: Entity discovery and prominence
   - Search: Detailed relationships and context
   - Comprehensive, actionable answer

## Best Practices

1. **Always specify the sequence**: Graph first, then search
2. **Be explicit about combining**: "Combine both results"
3. **State your goal**: "I want to understand X"
4. **Ask for both**: "Use both graph and semantic search"
5. **Request synthesis**: "Give me a comprehensive overview combining both"

## Common Patterns

### Pattern 1: Discovery → Details
```
Graph query → Semantic search → Combine
```

### Pattern 2: Entity → Context
```
Find entities → Get context → Synthesize
```

### Pattern 3: Structure → Content
```
Graph structure → Document content → Full picture
```

## Troubleshooting

### Claude Only Uses One Tool

**Fix:** Be more explicit:
```
I want you to use BOTH tools:
1. First obsidian_graph_query
2. Then obsidian_semantic_search
3. Then combine the results
```

### Results Don't Combine

**Fix:** Ask for synthesis:
```
After using both tools, combine the insights into a single comprehensive answer.
```

### Wrong Tool Order

**Fix:** Specify sequence:
```
Step 1: Use obsidian_graph_query
Step 2: Use obsidian_semantic_search
Step 3: Combine
```

