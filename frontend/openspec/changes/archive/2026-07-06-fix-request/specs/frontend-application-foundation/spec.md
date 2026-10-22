## MODIFIED Requirements

### Requirement: HTTP client boundary

The frontend application SHALL provide a shared request client for API calls that aligns with the current backend API response envelope and Cookie Session authentication model.

#### Scenario: Cookie authenticated request is sent

- **WHEN** the request client sends API requests
- **THEN** it SHALL allow the browser to include the backend session cookie
- **AND** it SHALL NOT require a Bearer token from the auth store

#### Scenario: API response indicates failure

- **WHEN** an API request receives a backend API error body
- **THEN** the request client SHALL reject the request and surface the top-level error message

#### Scenario: API returns unauthorized

- **WHEN** an API request receives unauthorized status
- **THEN** the request client SHALL clear auth state and move the user toward login

#### Scenario: Business API declares response type

- **WHEN** a business API method calls the shared request client
- **THEN** it SHALL declare only the unwrapped response data type and SHALL NOT require Axios response-generic workarounds

### Requirement: Development mock API

The frontend application SHALL provide a development mock API boundary using Vite.

#### Scenario: Developer runs dev server

- **WHEN** the app runs in Vite serve mode
- **THEN** mock API handlers SHALL be available for foundation-level authentication flows

#### Scenario: Development auth mock responds

- **WHEN** foundation-level authentication mock handlers return success or failure
- **THEN** they SHALL return the same response envelope shape expected by the shared request client

#### Scenario: Production build runs

- **WHEN** the app is built for production
- **THEN** mock API handlers SHALL NOT be enabled as production API behavior

## ADDED Requirements

### Requirement: Session-based auth state

The frontend application SHALL model authentication state as a backend Cookie Session with current user data instead of a client-side Bearer token.

#### Scenario: Login succeeds

- **WHEN** the user submits valid credentials to `POST /api/auth/login`
- **THEN** the frontend SHALL store the returned user
- **AND** it SHALL NOT require a returned token

#### Scenario: Current session is checked

- **WHEN** protected routes need authentication state
- **THEN** the frontend SHALL validate the session through `GET /api/auth/me`
- **AND** it SHALL store the returned user when validation succeeds

#### Scenario: Session check is recently fresh

- **WHEN** a protected route checks authentication shortly after a successful session check
- **THEN** the frontend MAY reuse the recent session result instead of unconditionally calling `/api/auth/me`

#### Scenario: Session check is already in flight

- **WHEN** multiple route guards need session validation concurrently
- **THEN** the frontend SHALL reuse the in-flight `/api/auth/me` validation when possible

#### Scenario: Session validation fails

- **WHEN** `/api/auth/me` returns unauthorized
- **THEN** the frontend SHALL clear the stored user and move the user toward login

#### Scenario: Guest route checks session

- **WHEN** the user opens a guest-only route such as `/login`
- **THEN** the frontend SHALL use session validation to redirect already authenticated users away from the guest-only route
