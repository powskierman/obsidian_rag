---
name: Gateway Deployment
description: Manage the API Gateway and service containers.
---

# Gateway Deployment Skill

This skill manages the lifecycle of the Docker-based API Gateway and Graph Service.

## Goal
To safely deploy, restart, and validate the backend services without causing downtime for the frontend (where possible) or leaving the system in a broken state.

## Tools & Scripts
*   **Docker:** `docker compose`
*   **Health Check:** `curl http://localhost:4000/api/v1/health`

## Instructions

1.  **Build**
    *   Run `docker compose build graph-service`
    *   Watch for compile errors in the python build steps.

2.  **Deploy**
    *   Run `docker compose up -d graph-service`
    *   Wait 15-30 seconds for the service to initialize (loading the graph pickle takes time).

3.  **Validation**
    *   Run `curl -v http://localhost:4000/api/v1/health`
    *   **Success Criteria:** Response code `200` AND body contains `"graph_loaded": true`.

4.  **Troubleshooting**
    *   If health check fails (503 or Connection Refused):
        *   Run `docker compose logs --tail=50 graph-service`
        *   Look for `ModuleNotFoundError` or `PickleError`.

## Constraints
*   Do not leave the service stopped (`docker compose down`) unless you are doing a full reset.
*   Always verify the `/health` endpoint after a deployment.
