# one‑shot reset script:

  - ```Scripts/vault_management/reset_benchmark_lightrag.sh```

 ### Usage:

  ```
OBSIDIAN_BENCH_VAULT_PATH=/tmp/obsidian_subset \
LIGHTRAG_BENCH_DIR=/tmp/lightrag_benchmark_db \
Scripts/vault_management/reset_benchmark_lightrag.sh
  ```

  #### Then run the async benchmark:

```
LIGHTRAG_FORCE_REINDEX=1 \
INDEXING_BENCHMARK_LIGHTRAG=1 \
LIGHTRAG_SERVICE_URL=http://localhost:8003 \
OBSIDIAN_TEST_VAULT=/tmp/obsidian_subset \
LIGHTRAG_VAULT_PATH=/app/vault \
LIGHTRAG_TEST_TIMEOUT=10800 \
pytest tests/integration/test_lightrag_indexing_benchmark.py -m integration
```
## The script:

  #### 1. Stops the benchmark container

  `docker compose -f docker-compose.yml -f docker-compose.benchmark.yml stop lightrag-benchmark`

  #### 2. Removes the container (ensures fresh start)

  `docker compose -f docker-compose.yml -f docker-compose.benchmark.yml rm -f lightrag-benchmark
  `

  #### 3. Resets benchmark data (optional but clean)

  `rm -rf /tmp/lightrag_benchmark_db`
  `mkdir -p /tmp/lightrag_benchmark_db`


  #### 4. Ensures subset vault exists

  `ls -la /tmp/obsidian_subset`

  #### 5. Rebuilds the benchmark image

  `docker compose -f docker-compose.yml -f docker-compose.benchmark.yml build lightrag-benchmark`

  #### 6. Relaunches the benchmark service

  `docker compose -f docker-compose.yml -f docker-compose.benchmark.yml up -d lightrag-benchmark`

  #### 7. Runs the async benchmark test

  ```LIGHTRAG_FORCE_REINDEX=1 \
  INDEXING_BENCHMARK_LIGHTRAG=1 \
  LIGHTRAG_SERVICE_URL=http://localhost:8003 \
  OBSIDIAN_TEST_VAULT=/tmp/obsidian_subset \
  LIGHTRAG_VAULT_PATH=/app/vault \
  LIGHTRAG_TEST_TIMEOUT=10800 \
  pytest tests/integration/test_lightrag_indexing_benchmark.py -m integration
  ```
