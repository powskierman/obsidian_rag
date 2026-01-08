# Disable Docker Obsidian Service

If you run Obsidian locally and do not want the Docker Obsidian server, remove or comment out that service in `docker-compose.yml`, then restart:

```bash
docker compose down
docker compose up -d
```
