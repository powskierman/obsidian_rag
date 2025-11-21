# KET-RAG Analysis

**Status**: ❌ Not Recommended  
**Last Updated**: 2025-11-21

## Summary

KET-RAG is a cost-efficient Graph-RAG framework, but **implementation complexity outweighs benefits** for our 1,771-note vault.

## What is KET-RAG?

Multi-granular indexing with two graphs:
1. **Skeleton Graph** - Knowledge graph from key documents only (uses PageRank)
2. **Keyword Graph** - Lightweight keyword→text mappings

**Benefits**: 20% cost reduction, 32% better query quality, excellent multi-hop reasoning

## Why Not Now?

| Factor | Current | With KET-RAG |
|--------|---------|--------------|
| Simplicity | ✅ High | ❌ Low |
| Implementation | ✅ Done | ❌ 2-4 weeks |
| Maintenance | ✅ Easy | ❌ Complex |
| Cost | 💰 Moderate | ✅ 20% cheaper |
| Quality | ✅ Good | ✅ 32% better |

**Our current setup already works well:**
- Hybrid search combines vector + full graph
- 7,795 documents indexed successfully
- System handles complex medical queries

**KET-RAG makes sense when:**
- Vault exceeds 10,000+ notes
- Budget requires 20%+ cost reduction
- Multi-hop reasoning quality issues emerge

## Better Next Steps

1. **Optimize current graph**: Tune entity extraction in `claude_graph_builder.py`
2. **Monitor performance**: Track query time, accuracy, costs
3. **Fine-tune retrieval**: Adjust similarity thresholds, chunk sizes

## References

- [KET-RAG Paper](https://arxiv.org/abs/2403.19269)
- Current: `docker-compose.yml`, `index_vault.py`, `claude_graph_builder.py`

**Next Review**: When vault reaches 5,000+ notes
