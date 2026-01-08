# Mac Mini Networking Fix

If containers cannot reach `host.docker.internal` or local services, rebuild with the correct host mapping:

```bash
docker compose down
docker compose up -d --build
```

If you still see network errors, verify Docker Desktop is running and the Mac mini firewall allows Docker traffic.
