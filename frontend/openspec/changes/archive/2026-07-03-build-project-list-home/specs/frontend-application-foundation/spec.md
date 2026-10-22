## MODIFIED Requirements

### Requirement: Minimal foundation pages

The frontend application SHALL include minimal Login and Home route foundations for validating routing, layout and authentication flow, while allowing later business capabilities to replace the Home page content.

#### Scenario: Login succeeds through mock API

- **WHEN** the user submits valid login credentials on the Login page
- **THEN** the application SHALL call the auth API, store token and user state, and navigate to `/home`

#### Scenario: Home page renders before business replacement

- **WHEN** no later business capability has replaced `/home`
- **THEN** the application SHALL render a minimal Home page that validates protected routing and layout rendering

#### Scenario: Home page is replaced by business capability

- **WHEN** a later approved capability defines `/home` business content
- **THEN** the frontend application SHALL allow that capability to own the Home page content without changing the protected route contract

### Requirement: Foundation excludes business project features

The frontend foundation SHALL NOT include project-list business functionality as part of the foundation capability itself.

#### Scenario: Foundation capability is reviewed

- **WHEN** reviewers inspect the foundation capability
- **THEN** project cards, project creation, project models, project APIs and project mocks SHALL remain outside the foundation capability and be specified by later business capabilities
