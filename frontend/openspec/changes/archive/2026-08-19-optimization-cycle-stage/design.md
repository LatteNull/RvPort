## Context

The backend creates or reactivates an optimization cycle when a source revision becomes active. It exposes a project overview, a paginated cycle list, and a cycle detail. Each response already aggregates the prior stages required to assess the current source revision. The workflow keeps the optimization node deferred and has no Drawer route.

## Goals / Non-Goals

**Goals:**

- Present the current optimization cycle as a concise project-level summary.
- Provide a server-paginated history list and an in-Drawer cycle detail view.
- Route users to existing build validation, automated test, and archive stages from appropriate summary actions.

**Non-Goals:**

- Do not add an optimization executor, create-cycle endpoint, or automatic reruns.
- Do not implement Benchmark, Profiling, RVV, or new performance-analysis backends.

## Decisions

- Use the backend-created cycle as the source of truth rather than introducing frontend task state. This preserves source-revision lineage and keeps the Drawer read-only.
- Use an 1100px Drawer because the historical cycle list is tabular; render a child detail view inside the same Drawer so navigation does not stack overlays.
- Model summary sections by the API's existing groups: migration inputs, assessment report, recheck, deployment, build, test, and test comparison. Missing data is displayed as unavailable, not inferred as a failure.
- Keep primary forward navigation in the Drawer footer. The current stage can guide users to build validation or automated testing; a ready cycle can guide users to archive.

## Risks / Trade-offs

- [Backend does not create optimization tasks] → The UI labels the node as a cycle overview and only links to existing executable stages.
- [Some summary fields can be absent] → Each section has a neutral empty state and avoids derived completion claims.
- [Cycle list can grow] → Use BaseTable with server pagination and no polling.
