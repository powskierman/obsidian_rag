# Docker Gateway Troubleshooting

## Health

```bash
curl -s http://localhost:4000/api/v1/health
```

## Rebuild Gateway

```bash
docker compose build api-gateway
docker compose up -d api-gateway
```

## Check Logs

```bash
docker compose logs -f api-gateway
```
