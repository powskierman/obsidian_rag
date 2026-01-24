# Directive: Deploy Gateway

## Metadata
- **Owner**: Connectors & MCP Track
- **Last Updated**: 2026-01-23
- **Related Scripts**: `docker compose`
- **Version**: 1.0.0

## Contract

### Purpose
Safely deploy, restart, and validate the backend services (Graph Service, API Gateway) without causing unnecessary downtime.

### Inputs
- **service** (string, optional): Service to deploy. Defaults to `"graph-service"`.
- **action** (string, optional): One of `"up"`, `"build"`, `"restart"`. Defaults to `"up"`.

### Outputs
- **status** (string): "success" or "failure".
- **health_check** (object): Response from `/health` endpoint.

### Preconditions
- Docker engine must be running.
- `docker-compose.yml` must be valid.

### Postconditions
- Service is running and reporting healthy.
- Graph is loaded (`graph_loaded: true`).

## Flow

1.  **Build (Optional but Recommended)**
    - If code changed, run `docker compose build <service>`.

2.  **Deploy**
    - Run `docker compose up -d <service>`.
    - Note: This is usually safe to run on a running system (recreates container only if config changed).

3.  **Wait**
    - Wait 15-30 seconds for initialization (Graph Service loads a large pickle file).

4.  **Validation**
    - Run `curl -v http://localhost:4000/api/v1/health` (or appropriate port).
    - **Success Criteria**: Status `200` AND body contains `"graph_loaded": true`.

## Error Handling

- **Health Check Fails (503/Connection Refused)**:
    - Check logs: `docker compose logs --tail=50 <service>`.
    - Common issues: `ModuleNotFoundError`, `PickleError`, or OOM (Out of Memory).
    - **Recovery**: Fix error, then retry Deploy.
- **Port Conflict**:
    - Check if port 4000/8000 is used by another process.

## Cost Profile
- **Local Resources**: High memory usage during graph load.
