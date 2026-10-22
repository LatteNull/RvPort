## 1. API and workflow integration

- [x] 1.1 Add typed frontend API client methods and response types for optimization overview, paginated cycles, and cycle detail endpoints.
- [x] 1.2 Add the optimization-closure node, route, and stage metadata to the project workflow without changing backend task orchestration.

## 2. Optimization cycle Drawer

- [x] 2.1 Implement the 1100px optimization cycle Drawer landing view with loading, unavailable, and current-cycle summary states.
- [x] 2.2 Render the backend-provided migration input, report, recheck, deployment, build, test, and test-comparison summaries with neutral handling for absent data.
- [x] 2.3 Implement server-paginated cycle history with BaseTable and in-Drawer navigation to a selected cycle's detailed summary.

## 3. Downstream navigation and verification

- [x] 3.1 Add context-appropriate navigation from cycle summaries to build validation, automated testing, and project archive without creating or rerunning optimization tasks.
- [x] 3.2 Add focused tests for API mapping, unavailable/current/detail states, pagination, and navigation behavior.
- [x] 3.3 Run the relevant frontend lint, typecheck, and test commands and resolve regressions caused by this change.
