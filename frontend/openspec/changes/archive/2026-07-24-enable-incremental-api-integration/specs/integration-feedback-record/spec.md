## ADDED Requirements

### Requirement: Browser-driven integration evidence

The project SHALL maintain a root-level Markdown integration record for each real frontend-backend test performed through the Vite development page.

#### Scenario: Real route test is recorded

- **WHEN** a frontend page calls a real backend route during integration
- **THEN** the record SHALL capture the frontend entry point, HTTP method and route, sanitized input summary, HTTP status, response summary, trace ID when supplied, and page-level conclusion

#### Scenario: Sensitive request material is protected

- **WHEN** a test includes credentials, cookies, CSRF tokens, session identifiers, or personal data
- **THEN** the record SHALL omit the sensitive values and retain only a non-sensitive summary necessary for reproduction

### Requirement: Integration status semantics

The integration record SHALL distinguish untested, passed, problematic, blocked, and temporarily unintegrated routes using a consistent status marker.

#### Scenario: Route is marked passed only after page verification

- **WHEN** a real backend response is successful and the frontend page exhibits the expected behavior
- **THEN** the route SHALL be marked `已通`

#### Scenario: Backend response alone does not mark a route passed

- **WHEN** a route has only been invoked directly outside the frontend page or the page behavior has not been verified
- **THEN** the route SHALL not be marked `已通`

### Requirement: Backend action handoff

The integration record SHALL maintain a consolidated list of unresolved backend-owned changes linked to the relevant route and test evidence.

#### Scenario: Contract mismatch is handed off to backend

- **WHEN** an integration test identifies a backend contract mismatch, missing field, incorrect status behavior, or unavailable endpoint
- **THEN** the record SHALL create a linked backend action item with priority, requested change, acceptance condition, owner, and related trace ID or test record

#### Scenario: Resolved backend action is closed

- **WHEN** a backend change has been retested through the frontend page and satisfies its acceptance condition
- **THEN** the linked action item SHALL be marked resolved and the route status SHALL be updated to reflect the retest result
