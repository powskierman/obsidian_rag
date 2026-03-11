1. Stop container

  docker compose -f docker-compose.yml -f docker-compose.benchmark.yml stop lightrag-benchmark

  2. Reset benchmark DB and log

  rm -rf /tmp/lightrag_benchmark_db
  mkdir -p /tmp/lightrag_benchmark_db
  docker compose -f docker-compose.yml -f docker-compose.benchmark.yml rm -f lightrag-benchmark

  3. Start container with env file + mounts

  OBSIDIAN_BENCH_VAULT_PATH=/tmp/obsidian_subset \
  LIGHTRAG_BENCH_DIR=/tmp/lightrag_benchmark_db \
  docker compose --env-file .env.benchmark -f docker-compose.yml -f docker-compose.benchmark.yml up -d lightrag-benchmark

  4. Verify vault mount

  docker exec -it obsidian-lightrag-benchmark ls -la /app/vault | head

  5. Verify effective container env

  docker exec -it obsidian-lightrag-benchmark env | grep -E '^(LIGHTRAG_BATCH_SIZE|LIGHTRAG_BATCH_TIMEOUT|EMBED_ASYNC|LLM_ASYNC|LIGHTRAG_CHUNK_TOKENS|LIGHTRAG_CHUNK_OVERLAP|LIGHTRAG_MAX_DOC_CHARS|LLM_MAX_TOKENS|LLM_TEMPERATURE|LLM_PROVIDER|LLM_MODEL|EMBED_MODEL)='
  
  6. Run benchmark test

  LIGHTRAG_FORCE_REINDEX=1 \
  INDEXING_BENCHMARK_LIGHTRAG=1 \
  LIGHTRAG_SERVICE_URL=http://localhost:8003 \
  OBSIDIAN_TEST_VAULT=/tmp/obsidian_subset \
  LIGHTRAG_VAULT_PATH=/app/vault \
  LIGHTRAG_DIR=/tmp/lightrag_benchmark_db \
  LIGHTRAG_MAX_FILES=10 \
  LIGHTRAG_TEST_TIMEOUT=10800 \
  pytest tests/integration/test_lightrag_indexing_benchmark.py -m integration

  Troubleshooting:

  docker logs -f obsidian-lightrag-benchmark
  curl -s http://localhost:8003/index-progress | jq
  2. Verify Ollama is responding
  `ollama ps`
  `ollama list | rg qwen3`

  3. If it’s hung, reduce batch size to 1 and restart

  docker compose -f docker-compose.yml -f docker-compose.benchmark.yml stop
  lightrag-benchmark
  LIGHTRAG_BATCH_SIZE=1 LIGHTRAG_BATCH_TIMEOUT=1800 \
  docker compose -f docker-compose.yml -f docker-compose.benchmark.yml up -d
  lightrag-benchmark

  Then rerun the benchmark.

**cold cache run**. Do this on the MacBook:

  docker compose -f docker-compose.yml -f docker-compose.benchmark.yml stop lightrag-benchmark
  rm -rf /tmp/lightrag_benchmark_db
  mkdir -p /tmp/lightrag_benchmark_db
  docker compose -f docker-compose.yml -f docker-compose.benchmark.yml up -d lightrag-benchmark

  Then run the benchmark again (5)