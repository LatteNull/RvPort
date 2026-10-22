## 1. Integration Mode and Proxy

- [x] 1.1 Add explicit `dev:api` and `dev:mock` Vite modes that preserve all-Mock development by default.
- [x] 1.2 Configure integration-mode `/api` proxying to the local Docker backend at `http://127.0.0.1:8080` without changing request-client relative URLs or credentials settings.
- [x] 1.3 Add focused verification that integration mode proxies `/api` routes and mock mode serves Mock routes.

## 2. Mode-Based Routing

- [x] 2.1 Register Mock handlers only in the explicit Mock mode.
- [x] 2.2 Keep integration mode free of Mock handlers so all `/api` routes use the backend proxy.

## 3. Integration Record and Backend Handoff

- [x] 3.1 Extend the root Markdown integration record with a consolidated unresolved backend action list.
- [x] 3.2 Extend problem and test-record templates with browser entry point, sanitized evidence, trace ID, backend change request, priority, owner, and acceptance condition.
- [x] 3.3 Document the rule that only browser-verified real API calls can be marked `已通`, and that sensitive credentials or session material must not be recorded.

## 4. Verification and Handoff

- [x] 4.1 Run frontend type checks and focused tests for the changed Vite/Mock routing behavior.
- [x] 4.2 Start the Vite integration mode against the existing local Docker backend and verify the routing mechanism from a browser page without migrating a business module.
- [x] 4.3 Record the integration-mode verification outcome in the root Markdown document, including any backend-owned blocker.

## 5. Auth Integration Follow-up

- [x] 5.1 Show a backend-provided message for non-silent 401 responses while preserving silent session checks.
- [x] 5.2 Align the login-page development credential hints with the backend seed account.
- [x] 5.3 Redirect only `403 PASSWORD_CHANGE_REQUIRED` responses to a protected password-change route.
- [x] 5.4 Add the password-change page and update the cached session after a successful password change.
- [x] 5.5 Redirect generic 403 responses to a dedicated forbidden page while preserving the password-change exception.
- [x] 5.6 Route directly from the login response when `mustChangePassword` is set, and prevent password-change-required sessions from entering business routes.
- [x] 5.7 Align existing Auth form validation with backend required-field and password-policy rules.
- [x] 5.8 Group password-management and HTTP error pages under extensible page domains without changing their routes.
- [x] 5.9 Move the password route to `/settings/security/password` and preserve forced-password-change redirects.
- [x] 5.10 Align the logout action with the backend `loggedOut` response contract and preserve local state on failure.
- [x] 5.11 Align the project-list client with the backend pagination contract and retain paging metadata.
- [x] 5.12 Load additional project-list pages on scroll using the backend `hasMore` pagination contract.
- [x] 5.13 Align the project-create form and request payload with the backend-supported basic project fields.
- [x] 5.14 Let HomePage handle post-create navigation and route directly to the newly created project detail page.
- [x] 5.15 Centralize backend project display mappings, including lifecycle stages and architectures, and use them in the project list.
- [x] 5.16 Hide deferred project-workflow nodes and retain only the current MVP analysis path.
- [x] 5.17 Drive the current MVP workflow view from the implemented project overview endpoint until backend workflow APIs are available.
- [x] 5.18 Populate the project-detail overview cards from implemented project, source, and environment summary fields.
- [x] 5.19 Reuse the project architecture-flow presentation in list cards and the project-detail overview.
- [x] 5.20 Reshape the project-detail overview around project identity, pipeline progress, stage context, and dynamic execution or next-action data.
- [x] 5.21 Refine the project-detail overview into persistent project, stage, task, and next-action cards using implemented overview domain summaries.
- [x] 5.22 Subscribe to the implemented project task-event SSE stream from the project-detail page without coupling events to Workflow state.
- [x] 5.23 Align the project-creation drawer with the implemented project detail and update APIs, removing its unavailable workflow-stage calls.
- [x] 5.24 Align environment list and create/update response handling with the implemented environment API contract.
- [x] 5.25 Align source artifact management with the implemented source revision, archive upload, Git-sync task, and activation APIs.
- [x] 5.26 Consume environment check basic-info responses in the environment UI and remove the ordinary collection action.
- [x] 5.27 Support jump-host environments and jump-host selection in the environment configuration flow.
- [x] 5.28 Simplify SBOM and knowledge-base scan configuration to the currently required inputs and defaults.
- [x] 5.29 Redirect gateway failures (`502`/`503`/`504`) to a dedicated error page while keeping endpoint-specific `500` failures in their page-level error state.
- [x] 5.30 Submit environment checks from a compact action-level confirmation instead of a dedicated drawer view.
- [x] 5.31 Simplify source artifact management to the single current source flow and hide internal revision controls.
- [x] 5.32 Treat Project and Environment drawer footer actions as local workflow navigation rather than unavailable backend stage-advance calls.
- [x] 5.33 Explicitly reload the environment list after submitting an environment check instead of relying on query-cache invalidation.
- [x] 5.34 Enable environment script execution only after a successful full environment check has produced a basic-info snapshot.
- [x] 5.35 Require an explicit SSH username for environment creation and remove the implicit `root` request fallback.
- [x] 5.36 Populate SBOM analysis inputs from successfully checked source and target environments, then submit their backend-required snapshot IDs.
- [x] 5.37 Align the SBOM component-result table with the backend `sourceComponentType` field instead of presenting it as a source path.
- [x] 5.38 Disable retained React Query data for environment-drawer lists, form options, and execution details so every open uses fresh backend data.
- [x] 5.39 Refactor BaseTable to request fresh data for each table instance while using Ant Design loading over the last successful in-instance result for stable pagination.
- [x] 5.40 Centralize empty-value, timestamp, and label-option display helpers and use them in environment, project-card, and SBOM views.
