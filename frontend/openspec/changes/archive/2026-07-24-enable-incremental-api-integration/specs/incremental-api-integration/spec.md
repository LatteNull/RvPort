## ADDED Requirements

### Requirement: Integration-mode API proxy

The frontend SHALL provide a Vite integration mode on the development-server workflow that proxies all `/api` requests to the local backend at `http://127.0.0.1:8080` while preserving the browser-visible `/api` request path.

#### Scenario: API route uses the local backend

- **WHEN** the frontend runs in integration mode and the browser requests an `/api` route
- **THEN** Vite SHALL forward the request to the local backend and return the backend response to the browser

#### Scenario: Existing request-client semantics remain unchanged

- **WHEN** a frontend API module invokes the request client in integration mode
- **THEN** it SHALL continue to use its existing relative `/api` base URL, credentials behavior, and CSRF request flow

### Requirement: Mock-mode API handling

The frontend SHALL provide an explicit Mock mode that registers the existing Mock handlers without a backend `/api` proxy.

#### Scenario: Existing Mock route uses Mock data

- **WHEN** the frontend runs with `dev:mock` and the browser requests an existing Mock `/api` route
- **THEN** Vite SHALL return the Mock response without a backend request

#### Scenario: Mode selection is not implemented in application code

- **WHEN** a page or API module makes an existing relative `/api` request
- **THEN** the selected Vite mode SHALL determine its target without route-level conditions in the application code

### Requirement: Password-change enforcement

The frontend SHALL use the login response's `mustChangePassword` value to direct a user to a protected password-change page before entering business routes. It SHALL also redirect an authenticated user to that page when the backend returns `403 PASSWORD_CHANGE_REQUIRED`.

#### Scenario: Login requires a password change

- **WHEN** `/api/auth/login` succeeds and its user summary has `mustChangePassword: true`
- **THEN** the frontend SHALL cache the user and navigate directly to `/settings/security/password` without calling `/api/auth/me` solely for that navigation decision

#### Scenario: Restored session requires a password change

- **WHEN** a user with `mustChangePassword: true` opens or refreshes a business route
- **THEN** the route guard SHALL redirect the user to `/settings/security/password`

#### Scenario: Password change is required

- **WHEN** a real backend API response has status `403` and code `PASSWORD_CHANGE_REQUIRED`
- **THEN** the frontend SHALL redirect to `/settings/security/password` without treating it as a generic permission error

#### Scenario: Password change succeeds

- **WHEN** the user submits a valid current password and a valid new password on `/settings/security/password`
- **THEN** the frontend SHALL call `/api/auth/change-password`, update its cached user from the response, and navigate to `/home`

#### Scenario: Auth form input is invalid

- **WHEN** a user submits an Auth form with an empty required value, an all-whitespace password, or a new password that violates the backend password policy
- **THEN** the frontend SHALL show a form validation error and SHALL NOT send the request

### Requirement: Logout contract handling

The frontend SHALL send a CSRF-protected `POST /api/auth/logout` request and clear its local session only after the backend confirms `loggedOut: true`.

#### Scenario: Logout succeeds

- **WHEN** the backend returns `{ loggedOut: true }` for `POST /api/auth/logout`
- **THEN** the frontend SHALL clear its cached user, show a success message, and replace the current route with `/login`

#### Scenario: Logout fails

- **WHEN** `POST /api/auth/logout` fails or does not confirm `loggedOut: true`
- **THEN** the frontend SHALL retain its cached user and show the request error or an explicit failure message

### Requirement: Forbidden-route handling

The frontend SHALL redirect a generic backend `403` response to a dedicated `/403` page.

#### Scenario: Generic permission denial

- **WHEN** a real backend API response has status `403` and its code is not `PASSWORD_CHANGE_REQUIRED`
- **THEN** the frontend SHALL redirect to `/403`
