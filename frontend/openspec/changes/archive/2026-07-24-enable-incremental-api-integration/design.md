## Context

The frontend is developed through the Vite server on `http://localhost:5173`. The local Docker stack already exposes the real backend on `http://localhost:8080` and includes its Postgres, Redis and RabbitMQ dependencies. The existing Vite configuration enables `vite-plugin-mock` for every development-server run and has no `/api` proxy; the frontend therefore cannot selectively exercise the real backend.

The frontend request client already uses relative `/api` URLs and `withCredentials: true`. Its unsafe-request interceptor obtains and caches CSRF metadata. These semantics must remain unchanged during integration.

The root Markdown integration record is the collaboration artifact for the frontend and backend teams. It must describe actual browser-driven behavior without exposing passwords, session cookies or full sensitive payloads.

## Goals / Non-Goals

**Goals:**

- Make a Vite integration mode that sends all `/api` requests to the local Docker backend, alongside an explicit Mock mode that serves all existing Mock handlers.
- Preserve same-origin browser behavior for cookies and CSRF by proxying through Vite.
- Treat session-dependent routes, initially Auth, as an atomic route group when they move to the real backend.
- Define an operational record format that yields a concise, actionable backend change list from real browser tests.

**Non-Goals:**

- Replacing Mock data for all modules in one change.
- Changing backend API contracts, deploying the backend remotely, or changing the production Nginx proxy on port `8081`.
- Automatically harvesting browser requests or persisting credentials, cookies, or complete sensitive response bodies in the Markdown record.
- Completing a specific business flow such as Auth within this initial infrastructure change.

## Decisions

### 1. Use a dedicated Vite integration mode, not a different frontend runtime

The integration frontend remains on port `5173`; an explicit Vite mode selects its data source. `dev:mock` enables all Mock handlers, while `dev:api` enables backend proxying.

This is preferred over using the Dockerized frontend on port `8081`, because source changes need hot reload and the Vite server is the actual V1 development surface. It is also preferred over pointing `VITE_API_BASE_URL` directly at `http://localhost:8080`, because direct browser requests introduce CORS and cross-origin cookie/CSRF concerns.

### 2. Proxy all `/api` routes to the local backend in integration mode

In integration mode, Vite proxies `/api` to `http://127.0.0.1:8080` and does not register Mock handlers. In Mock mode, Mock handlers are registered and there is no backend proxy.

The route boundary is thus:

```text
Browser -> /api/* -> Vite
                     |-- integration mode -> local backend :8080
                     `-- mock mode -> Mock response
```

This preserves the existing request client's relative base URL, `withCredentials`, and CSRF header behavior.

### 3. Keep mode selection out of application code

Vite owns the data-source decision. API modules and pages retain their existing relative `/api` calls, and neither has route-level environment conditions. A future partial module migration can be introduced only after the backend contract is stable, rather than adding a route manifest preemptively.

### 4. Record browser-driven integration evidence and backend action items separately

For every real route test, the root Markdown document records the frontend entry point, sanitized input summary, HTTP status, response summary, trace ID when returned, and page-level conclusion. An endpoint is marked `已通` only when the request and expected UI behavior both succeed.

Any contract mismatch creates a linked issue with backend modification request, priority, responsible side, acceptance condition, and the related test record/trace ID. A top-level backend action list aggregates only unresolved backend-owned items. This is preferred over placing all details in a single endpoint table, which makes backend handoff difficult.

### 5. Use the login response for the first navigation decision

The login response already contains the user summary, including `mustChangePassword`. After a successful login, the frontend stores that user and immediately navigates to `/settings/security/password` when the flag is true; otherwise it navigates to `/home`. It does not call `/auth/me` solely to make this decision.

`/auth/me` remains the service-side source of truth for cold starts, refreshes and expired session recovery. The root business route also requires a session without `mustChangePassword`, so a direct URL, page refresh or restored session cannot bypass the password-change screen. The password route itself only requires authentication.

## Risks / Trade-offs

- [Mock middleware conflicts with the backend proxy] -> Register Mock handlers only in Mock mode, then verify one route in each mode before beginning module integration.
- [An unfinished backend endpoint is used in integration mode] -> Switch the whole development server back to `dev:mock` until that module is ready for real integration.
- [Backend is unavailable or partially initialized] -> Preserve the Mock route as rollback; mark the integration record as `阻塞` rather than changing UI behavior.
- [Sensitive values are copied into the record] -> Record field names, summaries and trace IDs only; redact credentials, cookie values, tokens and personal data.
- [Document drifts from actual status] -> Update the relevant endpoint row and evidence row immediately after each browser test; backend action list is generated by linking unresolved issues, not duplicated free text.

## Migration Plan

1. Introduce explicit Mock and integration Vite modes; only integration mode configures the `/api` proxy.
2. Verify one backend route in integration mode and one Mock route in Mock mode from `5173`.
3. Establish the Markdown backend action-list and issue fields before beginning a business module.
4. Start real module integration only after the corresponding backend contract is ready, recording each actual browser test.

Rollback is mode-level: restart the Vite server with `dev:mock`. No browser component code or backend deployment must be rolled back.

## Open Questions

- Whether a future partially implemented backend module needs a separate local Mock server, rather than frontend route-level mixing.
- Whether task/SSE endpoints require additional proxy configuration once their backend contracts are ready.
