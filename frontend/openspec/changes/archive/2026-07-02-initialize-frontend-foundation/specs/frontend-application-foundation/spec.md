## ADDED Requirements

### Requirement: Frontend package and toolchain

RvPort-Frontend SHALL provide a pnpm-managed React, TypeScript and Vite application under `frontend/`.

#### Scenario: Developer runs local scripts

- **WHEN** a developer works in `frontend/`
- **THEN** the package SHALL expose scripts for local dev, build, preview, lint, format check, formatting and TypeScript typecheck

#### Scenario: Application resolves source aliases

- **WHEN** application code imports source modules with `@/...`
- **THEN** Vite and TypeScript SHALL resolve `@` to `src`

### Requirement: Application providers

The frontend application SHALL initialize React with a top-level application shell that provides TanStack Query and React Router.

#### Scenario: Application starts

- **WHEN** the browser loads the Vite application
- **THEN** React SHALL render an App containing `QueryClientProvider` and `RouterProvider`

### Requirement: Router foundation

The frontend application SHALL provide a standalone router module with `/login` and `/home` routes.

#### Scenario: Unauthenticated user opens protected route

- **WHEN** no auth token exists and the user opens `/home`
- **THEN** the route loader SHALL redirect the user to `/login`

#### Scenario: Authenticated user opens login route

- **WHEN** an auth token exists and the user opens `/login`
- **THEN** the route loader SHALL redirect the user to `/home`

#### Scenario: User opens root route

- **WHEN** the user opens `/`
- **THEN** the router SHALL redirect to `/home`

### Requirement: Minimal foundation pages

The frontend application SHALL include minimal Login and Home pages for validating routing, layout and authentication flow.

#### Scenario: Login succeeds through mock API

- **WHEN** the user submits valid login credentials on the Login page
- **THEN** the application SHALL call the auth API, store token and user state, and navigate to `/home`

#### Scenario: Home page renders

- **WHEN** an authenticated user reaches `/home`
- **THEN** the application SHALL render a minimal Home page that does not include project-list business functionality

### Requirement: Server state and local state boundaries

The frontend application SHALL use TanStack Query for server state and Zustand for local authentication state.

#### Scenario: Server data is requested

- **WHEN** a page needs server-owned data
- **THEN** the page SHALL use TanStack Query query or mutation APIs rather than owning request lifecycle with `useEffect + useState`

#### Scenario: Authentication state changes

- **WHEN** login or logout changes local auth state
- **THEN** the application SHALL store token and user state in a Zustand auth store

### Requirement: HTTP client boundary

The frontend application SHALL provide a shared Axios request client for API calls.

#### Scenario: Authenticated request is sent

- **WHEN** an auth token exists in the auth store
- **THEN** the request client SHALL attach it to outgoing API requests

#### Scenario: API response indicates failure

- **WHEN** the API response envelope indicates a non-success result
- **THEN** the request client SHALL reject the request and surface an error message

#### Scenario: API returns unauthorized

- **WHEN** an API request receives unauthorized status
- **THEN** the request client SHALL clear auth state and move the user toward login

### Requirement: Development mock API

The frontend application SHALL provide a development mock API boundary using Vite.

#### Scenario: Developer runs dev server

- **WHEN** the app runs in Vite serve mode
- **THEN** mock API handlers SHALL be available for foundation-level authentication flows

#### Scenario: Production build runs

- **WHEN** the app is built for production
- **THEN** mock API handlers SHALL NOT be enabled as production API behavior

### Requirement: Styling foundation

The frontend application SHALL use SCSS, CSS Modules and CSS Variables for styling.

#### Scenario: Component styles are authored

- **WHEN** a page or component needs local styles
- **THEN** those styles SHALL use `*.module.scss`

#### Scenario: Semi theme color is customized

- **WHEN** the foundation needs to customize Semi semantic colors
- **THEN** it SHALL use globally imported CSS Variables rather than a Semi DSM theme package

#### Scenario: Global reset is applied

- **WHEN** global reset styles are loaded
- **THEN** they SHALL avoid unintentionally overriding Semi component internals

### Requirement: Code quality automation

The frontend application SHALL configure formatting, linting, import ordering and pre-commit checks.

#### Scenario: Developer saves a source file

- **WHEN** a developer saves a TypeScript or React file in supported editors
- **THEN** ESLint auto-fix SHALL be able to sort imports according to project rules

#### Scenario: Developer validates the foundation

- **WHEN** a developer runs quality checks
- **THEN** format check, lint and typecheck SHALL pass

### Requirement: Foundation excludes business project features

The frontend foundation SHALL NOT include project-list business functionality.

#### Scenario: Foundation change is reviewed

- **WHEN** reviewers inspect the foundation change
- **THEN** project cards, project creation, project models, project APIs and project mocks SHALL be out of scope
