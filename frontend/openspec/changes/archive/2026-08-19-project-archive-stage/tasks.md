## 1. API and workflow integration

- [x] 1.1 Add typed frontend API client methods and response types for archive overview, creation, paginated history, detail, package download, and item download endpoints.
- [x] 1.2 Add the archive node, route, and stage metadata to the project workflow without changing backend archive composition or task execution.

## 2. Archive Drawer

- [x] 2.1 Implement the 1100px archive Drawer landing view with loading, no-archive, latest-archive, running, and failed status states.
- [x] 2.2 Implement explicit confirmation for archive creation, including disabled guidance when the project has no active source revision.
- [x] 2.3 Refresh archive overview and history after create or manual refresh without introducing task polling.
- [x] 2.4 Implement server-paginated archive history with BaseTable and an in-Drawer archive detail view for item metadata.

## 3. Download and verification

- [x] 3.1 Provide package and per-item format downloads only for formats returned by the backend.
- [x] 3.2 Add focused tests for empty/latest/create/detail/download states, server pagination, and no-active-source handling.
- [x] 3.3 Run the relevant frontend lint, typecheck, and test commands and resolve regressions caused by this change.
