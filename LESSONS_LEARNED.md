# Lessons Learned

## Scope

This project integrated a self-hosted Mem0 stack with an existing Dockerized OpenWebUI instance without modifying OpenWebUI source code. The working topology is:

- `mem0-owui` as a sidecar service stack
- OpenWebUI as the unchanged upstream application
- local OpenAI-compatible model service on `host.docker.internal:1234/v1`
- Pipelines provider on `host.docker.internal:9099`

The core architectural conclusion is that this integration should be treated as an overlay/sidecar customization, not as an in-place fork of OpenWebUI.

## What Worked

- Running Mem0 as an independent stack was the right choice. It kept the memory logic isolated from OpenWebUI upgrades.
- Using OpenAI-compatible local endpoints for both chat and embeddings reduced moving parts.
- Keeping `mem0-owui-selfhosted.py` and `pipelines/mem0_owui_thin.py` identical avoided drift between upload-compatible and mounted runtime variants.
- Verifying the full path with actual chat traffic was necessary. Simple health checks were not enough.

## Main Problems Encountered

### 1. Version mismatch between code and Mem0 runtime

The adapter code expected newer Mem0 APIs, but the container initially used `mem0ai==0.0.8`. This caused retrieval failures and `500` errors from the control-plane path.

Lesson:

- lock the Mem0 library version to the actual API surface used by the adapter
- treat adapter code and dependency versions as one unit

### 2. Embedding dimension mismatch

The local embedding model returned `1024` dimensions, but the collection setup was not explicitly aligned with that value. This is easy to miss and produces broken vector-store behavior.

Lesson:

- never rely on implicit embedding dimensions
- make embedding dimension an explicit config value and pass it through to the vector store

### 3. Container networking assumptions

OpenWebUI ran inside Docker, but some provider settings still pointed to `127.0.0.1`. From inside the container, that targeted the container itself, not the host model service.

Lesson:

- for Dockerized OpenWebUI, host services must use `host.docker.internal`, not `localhost` or `127.0.0.1`

### 4. Pipelines provider was accidentally treated as a normal model provider

When the OpenWebUI provider config for `9099` had `model_ids=["mem0_owui_thin"]`, OpenWebUI stopped reading the real `/models` response from the pipelines server. That meant it did not see the pipeline metadata:

- `type=filter`
- `pipelines=["*"]`
- `priority=0`

As a result, `mem0_owui_thin` was misclassified as a selectable model instead of a global filter.

Lesson:

- for a pipelines provider, do not pre-fill `model_ids` if OpenWebUI needs to discover pipeline metadata from `/models`
- let OpenWebUI read the actual pipelines response

### 5. "Looks healthy" did not mean "works end to end"

At different stages, all of the following were true while the integration was still effectively broken:

- containers were up
- `/ready` returned healthy
- model lists loaded
- OpenWebUI showed providers

The real confirmation only came after proving:

- `filter/inlet` was called from OpenWebUI
- `filter/outlet` was called after completion
- the worker consumed the event
- a later prompt retrieved the stored memory

Lesson:

- always test the complete lifecycle, not just startup health

## Runtime Integration Strategy

The safest strategy for this project is:

1. Keep OpenWebUI source code unchanged.
2. Put custom logic in `mem0-owui`.
3. Use runtime configuration on the OpenWebUI side.
4. Reapply runtime configuration with an idempotent script when needed.

This avoids turning OpenWebUI into a long-lived local fork and makes upstream updates much safer.

## Recommended Rules Going Forward

- Treat OpenWebUI as upstream and mostly read-only.
- Keep all Mem0-specific logic in this repository.
- Use runtime config, container config, or external scripts before considering any upstream source edit.
- If a change must target OpenWebUI behavior, prefer:
  - provider configuration
  - `webui.db` runtime updates
  - compose overrides
  - sidecar services
- Avoid hidden assumptions about:
  - hostnames
  - embedding dimensions
  - provider discovery rules
  - dependency versions

## Validation Checklist

After any update, verify in this order:

1. `docker compose -f docker-compose.example.yml up -d --build`
2. `http://127.0.0.1:8081/ready` returns healthy
3. `http://localhost:9099/models` returns `pipelines: true`
4. OpenWebUI provider config for `9099` keeps `model_ids` empty
5. OpenWebUI `/api/v1/pipelines/list` includes the `9099` provider
6. a normal chat model such as `qwen3.5-9b` triggers `filter/inlet`
7. `/api/chat/completed` triggers `filter/outlet`
8. `memory-worker` consumes the event
9. a later prompt retrieves the stored memory

## Current Known Residual Risk

The primary memory path is working, but graph enhancement can still degrade to vector-only mode in some runs.

Lesson:

- the system is operational even when graph augmentation is degraded
- graph-specific behavior should be treated as a secondary hardening step, not a blocker for initial rollout

## Final Takeaway

The most important project lesson is architectural:

keep the customization at the edge, not inside the upstream core.

For this project, that means:

- Mem0 stays as a sidecar
- OpenWebUI stays update-friendly
- runtime config is preferred over source edits
- end-to-end validation is mandatory
