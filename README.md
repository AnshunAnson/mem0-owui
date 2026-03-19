# mem0-owui v1

Async memory governance for OpenWebUI + mem0.

## Architecture

The v1 stack is fixed to:

`OpenWebUI -> Pipelines -> Control Plane -> Event Store(SQLite) -> Redis(RQ) -> Worker -> mem0(qdrant + neo4j)`

Key properties:

- Thin OpenWebUI pipeline only does retrieval injection and event posting.
- Control plane owns schema validation, dedupe, ledger writes, queue handoff, and dispatcher retry for `received` / `queue_failed`.
- Worker owns `extract -> evolve(candidate) -> audit -> apply`.
- `apply` is serialized with Redis locks.
- `graph` is enhancement only. Vector writes stay primary and graph degradation does not block the main write.
- Replay is supported through `POST /memory/events/{event_id}/replay`.

## Repository Layout

- `app/`: control-plane API, worker jobs, SQLite store, queue, adapters, services.
- `pipelines/mem0_owui_thin.py`: uploadable OpenWebUI thin pipeline.
- `mem0-owui-selfhosted.py`: root-level copy of the thin pipeline for compatibility with the original upload flow.
- `docker-compose.example.yml`: example multi-service deployment.

## Public API

- `POST /memory/events`
- `GET /memory/events`
- `GET /memory/events/{event_id}`
- `POST /memory/events/{event_id}/replay`
- `GET /health`
- `GET /ready`

Internal endpoint used by the thin pipeline:

- `POST /internal/retrieval`

## Runtime Contracts

- `event_id` is the caller request id.
- `dedupe_key` is the service-side short-window receive idempotency key.
- `dedupe_key` includes a time bucket. Identical content outside the dedupe window is accepted as a new event.
- SQLite is initialized with:
  - `PRAGMA journal_mode=WAL`
  - `PRAGMA synchronous=NORMAL`
  - `PRAGMA busy_timeout=5000`
- `apply_id` is the final write completion marker. A successful `apply_id` is never rewritten.
- `target_id` must point to a stable mem0 memory id. Invalid update or merge actions are revised before apply.
- Repair worker is graph-only. It must not change memory content or create new primary memory.
- `/ready` reports minimum readiness from SQLite + Redis, and exposes richer dependency detail for Qdrant, Neo4j, mem0, and the local LLM endpoint.

## Quick Start

1. Copy [`.env.example`](/E:/Agent/mem0-owui-1.0.0/.env.example) to `.env` and adjust credentials.
2. Start the stack:

```bash
docker compose -f docker-compose.example.yml up -d --build
```

3. Upload [mem0-owui-selfhosted.py](/E:/Agent/mem0-owui-1.0.0/mem0-owui-selfhosted.py) to OpenWebUI Pipelines, or mount [pipelines/mem0_owui_thin.py](/E:/Agent/mem0-owui-1.0.0/pipelines/mem0_owui_thin.py) into a Pipelines container.
4. In OpenWebUI, point the pipeline to `http://host.docker.internal:8081`.
5. Verify control-plane health with `GET /health` and `GET /ready`.

## OpenWebUI Integration Notes

Your current Dockerized OpenWebUI instance can already resolve `host.docker.internal`, so the thin pipeline can reach a control plane running either on the host or on a different compose stack exposed through a host port such as `8081`.

If you run the Pipelines container separately, expose it on a host port such as `9099` and configure OpenWebUI to reach it via `http://host.docker.internal:9099`.

## Testing

Run the local suite with:

```bash
python -m pytest tests
```

## Legacy Files

`mem0-owui-managed.py` remains in the repo as a legacy artifact. The v1 implementation in this repository is the self-hosted async governance stack.

