## 1. Workflow and API foundation

- [x] 1.1 Enable the source comparison workflow node, add the source repair group around manual repair, and update edges to manual repair -> source comparison -> build validation while retaining manual repair -> source management feedback.
- [x] 1.2 Add typed frontend request helpers for creating a latest recheck and loading server-paginated source comparison difference items and details.
- [x] 1.3 Add shared status, difference-status, source-type, severity, and confidence display mappings needed by the source comparison views.

## 2. Source comparison Drawer

- [x] 2.1 Create the SourceCompare stage Drawer and connect it to stage routing with the 1100px table layout.
- [x] 2.2 Implement latest comparison loading states for missing source revisions, not-started, running, failed, and succeeded rechecks.
- [x] 2.3 Implement version context and compact resolved/unchanged/changed/new summary presentation.
- [x] 2.4 Implement the BaseTable-backed, server-paginated difference list with status, source type, severity, and confidence filters.
- [x] 2.5 Implement in-Drawer difference detail navigation with old/new finding records and matching metadata.
- [x] 2.6 Implement source-management navigation, recheck/retry actions, running-state refresh, and the successful transition to build validation.

## 3. Existing stage alignment and verification

- [x] 3.1 Remove latest comparison querying and summary rendering from ManualRepair, retaining offline repair guidance and the source-management entry.
- [x] 3.2 Add focused tests for source comparison status branches, filtered list behavior, detail navigation, and workflow transitions.
- [x] 3.3 Run frontend lint, typecheck, and relevant tests; resolve regressions.
