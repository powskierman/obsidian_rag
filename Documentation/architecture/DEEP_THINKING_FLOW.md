# Deep Thinking Flow

The API gateway exposes a WebSocket endpoint for the deep thinking agent:

- `ws://localhost:4000/api/v1/deep-research`

The agent orchestrates calls to vector and graph services for multi-step reasoning.

Use this only if you need long-form, multi-hop analysis; standard search modes are faster.

## Workflow Diagram

```mermaid
flowchart TD
    U["User Query"] --> P["Planner Agent<br/>Research plan (3-7 steps)"]
    P --> S["Retrieval Supervisor<br/>Execute searches (vault + web + graphs)"]
    S --> R["Reflection Agent<br/>Extract findings, assess confidence"]
    R --> C["Policy Agent<br/>Decide: continue / revise / finish"]
    C -->|continue| S
    C -->|finish| Y["Synthesizer Agent<br/>Final answer with citations + images"]
```
