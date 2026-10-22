## Context

The backend already creates an archive task from the active source revision, stores archive snapshots and items, and supports list, detail, archive-package download, and item download APIs. The frontend does not expose the archive node or these APIs.

## Goals / Non-Goals

**Goals:**

- Open the archive workflow node and show the latest archive state plus project archive history.
- Create a current archive with explicit confirmation and expose progress, failure, retry, detail, and download actions.
- Render archive item metadata and format-specific downloads in an in-Drawer detail view.

**Non-Goals:**

- Do not alter archive composition, task execution, stored artifacts, or project lifecycle status in the backend.
- Do not poll archive tasks; users refresh manually or by reopening the Drawer.

## Decisions

- Use the archive overview for the compact landing state and BaseTable for server-paginated history.
- Use a confirmation dialog before creating an archive because it creates an immutable project snapshot.
- Use the backend status as the only archive readiness signal; do not predict included artifacts in the frontend.
- Use direct backend download URLs for the archive package and item formats, allowing the browser to handle streamed file download.
- Use an 1100px Drawer because the history table and item detail need consistent width.

## Risks / Trade-offs

- [No active source revision] → Disable archive creation and direct users to source management.
- [Archive task is still running or failed] → Show its backend status with manual refresh/retry rather than polling.
- [Some archive items do not have downloadable files] → Show metadata and only offer formats provided by the API, with JSON metadata as supported by the backend.
