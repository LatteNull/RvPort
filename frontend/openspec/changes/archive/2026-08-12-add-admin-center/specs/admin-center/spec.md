## ADDED Requirements

### Requirement: Admin-center authorization and navigation

The frontend SHALL provide an `/admin/*` management module that is visible and accessible only to users with `isSuperAdmin: true`.

#### Scenario: Administrator enters the management center

- **WHEN** a super administrator selects “管理中心”
- **THEN** the frontend SHALL navigate to `/admin/users` and provide navigation to user management and mail configuration

#### Scenario: Non-administrator accesses an admin route

- **WHEN** a user without super-administrator permission opens an `/admin/*` route
- **THEN** the route guard SHALL redirect the user to `/403`

### Requirement: Administrator user management

The frontend SHALL allow a super administrator to list, filter, create, update, disable, reset passwords for, and resend invitations to ordinary users through the existing admin user APIs.

#### Scenario: Administrator manages a user

- **WHEN** an administrator submits a valid user-management action
- **THEN** the frontend SHALL call the corresponding `/api/admin/users` endpoint and refresh the displayed user list after success

### Requirement: Administrator mail configuration

The frontend SHALL allow a super administrator to view, update, and test the SMTP mail configuration without exposing a configured password value.

#### Scenario: Administrator saves mail configuration

- **WHEN** an administrator submits valid mail settings
- **THEN** the frontend SHALL update `/api/admin/configs/mail`, show the returned password-configured state, and SHALL NOT populate the password field from the response
