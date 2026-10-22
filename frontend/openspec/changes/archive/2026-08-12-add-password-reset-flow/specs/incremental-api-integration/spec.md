## ADDED Requirements

### Requirement: Password-reset API integration

The frontend SHALL expose typed API methods for password reset request and confirmation, and its development mock SHALL follow the same request and success-response contracts.

#### Scenario: Request API contract

- **WHEN** the password-reset request page is submitted
- **THEN** the API module SHALL send `POST /auth/password-resets/request` with `{ identifier }` and consume `{ accepted: true }`

#### Scenario: Confirmation API contract

- **WHEN** the password-reset confirmation page is submitted
- **THEN** the API module SHALL send `POST /auth/password-resets/confirm` with `{ token, newPassword }` and consume the returned user summary without persisting it as a login session

## MODIFIED Requirements

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

- **WHEN** the user submits a valid current password and a valid new password on `/settings/security/password` or from the personal-center password dialog
- **THEN** the frontend SHALL call `/api/auth/change-password`, invoke `POST /api/auth/logout`, clear its cached user, and replace the current route with `/login`

#### Scenario: Auth form input is invalid

- **WHEN** a user submits an Auth form with an empty required value, an all-whitespace password, or a new password that violates the backend password policy
- **THEN** the frontend SHALL show a form validation error and SHALL NOT send the request
