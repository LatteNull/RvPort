## Purpose

定义未登录用户通过邮件安全发起并完成密码重置的前端流程、隐私边界和异常反馈，避免泄露账户存在性或敏感凭据。

## Requirements

### Requirement: Login-page password-reset entry

The frontend SHALL provide an accessible “忘记密码” entry on the login page that navigates unauthenticated users to `/forgot-password`.

#### Scenario: User opens password reset request page

- **WHEN** an unauthenticated user activates “忘记密码” on the login page
- **THEN** the frontend SHALL navigate to `/forgot-password`

### Requirement: Password-reset request

The frontend SHALL provide a guest-accessible `/forgot-password` page that accepts one required identifier field for either username or email and submits it to `POST /api/auth/password-resets/request`.

#### Scenario: Request reset email

- **WHEN** a user submits a non-empty username or email
- **THEN** the frontend SHALL send `{ identifier }` to the password-reset request API and show the same success feedback regardless of account existence

#### Scenario: Identifier is empty

- **WHEN** a user submits the request form without an identifier
- **THEN** the frontend SHALL show a field validation error and SHALL NOT send a request

### Requirement: Password-reset confirmation

The frontend SHALL provide a guest-accessible `/reset-password` page that reads the reset token from the `token` query parameter and submits the new password to `POST /api/auth/password-resets/confirm`.

#### Scenario: Reset password successfully

- **WHEN** a user opens a reset link with a token and submits a valid new password and matching confirmation
- **THEN** the frontend SHALL send `{ token, newPassword }`, show a success feedback, and replace the current route with `/login`

#### Scenario: Reset token is missing

- **WHEN** a user opens `/reset-password` without a `token` query parameter
- **THEN** the frontend SHALL explain that the link is invalid and provide a path to request a new reset email without submitting the confirmation API

### Requirement: Password-reset request privacy

The frontend SHALL NOT persist reset tokens, new passwords, or identifier existence results in local or session storage.

#### Scenario: Request completes

- **WHEN** a password reset request or confirmation completes
- **THEN** the frontend SHALL retain no password or token in browser storage
- **AND** the reset page SHALL capture the initial token in page memory and remove it from the URL with history replacement
