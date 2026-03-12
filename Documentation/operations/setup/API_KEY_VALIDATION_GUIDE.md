# Claude API Key Validation

## Summary
Streamlit only reads environment variables at container start. If you update `.env`, restart the container and confirm the key is present inside the container.

## Steps

1. Update `.env` (project root):
   ```bash
   ANTHROPIC_API_KEY=sk-ant-...
   ```

2. Restart Streamlit:
   ```bash
   docker compose stop streamlit-ui
   docker compose up -d streamlit-ui
   ```

3. Verify the container has the same key:
   ```bash
   KEY_ENV=$(grep "^ANTHROPIC_API_KEY=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")
   KEY_DOCKER=$(docker compose exec -T streamlit-ui printenv ANTHROPIC_API_KEY | tr -d '\r')
   [ "$KEY_ENV" = "$KEY_DOCKER" ] && echo "Keys match" || echo "Keys differ"
   ```

## If You Still Get 401s
- Check that the key starts with `sk-ant-` and is active in the Anthropic console.
- Recreate the container if restart is not enough:
  ```bash
  docker compose stop streamlit-ui
  docker compose rm -f streamlit-ui
  docker compose up -d streamlit-ui
  ```
