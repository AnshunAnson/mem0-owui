# Thin Pipeline Upload

Use [mem0_owui_thin.py](/E:/Agent/mem0-owui-1.0.0/pipelines/mem0_owui_thin.py) as the uploadable OpenWebUI filter.

What it does:

- `inlet`: calls `POST /internal/retrieval` on the control plane and injects bounded memory context.
- `outlet`: calls `POST /memory/events` and returns immediately.

What it does not do:

- It does not talk directly to mem0.
- It does not enqueue Redis jobs.
- It does not run extraction, evolution, audit, or apply logic.

Recommended valve defaults:

- `control_plane_base_url=http://host.docker.internal:8081`
- `control_plane_timeout_seconds=5`
- `default_user_id=default_user`
- `default_project_id=default`
- `default_task_id=default`
