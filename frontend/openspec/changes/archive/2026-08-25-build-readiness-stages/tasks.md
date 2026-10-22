## 1. Data Contracts and Queries

- [x] 1.1 Add frontend API clients, request/response types, and query keys for build runs, build detail/logs, dependency analyses, dependency results, result detail, and artifacts.
- [x] 1.2 Add project-context selectors that resolve the active source revision and complete project-level source and target runtime environments without introducing temporary environment selection.
- [x] 1.3 Add shared status/currentness helpers that map backend task and record states to stage presentation, including non-current source or runtime-environment configuration.

## 2. x86 Build Stage

- [x] 2.1 Replace the static x86 branch of `BuildReadiness` with an `X86Build` Drawer that presents source revision, source environment, and source-deployment prerequisite as read-only context.
- [x] 2.2 Implement the x86 build configuration and submission flow, always creating `SOURCE_ONLY` build runs and validating command, working directory, timeout, and optional environment variables.
- [x] 2.3 Implement x86 build history, detail, task status, logs, cancel action where available, and explicit refresh using server-side pagination.

## 3. Dependency Analysis Stage

- [x] 3.1 Replace the static dependency branch of `BuildReadiness` with a `DependencyAnalysis` Drawer that shows the active source revision, qualifying x86 build, and target environment as read-only inputs.
- [x] 3.2 Implement dependency-analysis submission with prerequisite gating when a current successful x86 `SOURCE_ONLY` build or complete project runtime environment is unavailable.
- [x] 3.3 Implement paginated dependency-analysis history, result table filters, result detail/evidence view, and backend-provided artifact access.
- [x] 3.4 Show the latest dependency-analysis result by default and provide an explicit history-records entry.

## 4. Workflow Integration and Verification

- [x] 4.1 Route `x86-build` and `rv-dependency-analysis` to their independent Drawer modules and remove the static readiness controls.
- [x] 4.2 Drive both workflow-node statuses and prerequisite messaging from backend records while preserving the existing `x86-build -> rv-dependency-analysis -> report` topology.
- [x] 4.3 Add focused tests for `SOURCE_ONLY` submission, dependency-analysis prerequisite gating, currentness mapping, and manual refresh behavior without polling.
- [x] 4.4 Run the relevant frontend type check, lint, and test commands; resolve failures caused by this change.
