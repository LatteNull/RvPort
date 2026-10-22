## ADDED Requirements

### Requirement: Admin API integration

The frontend SHALL expose typed API methods and development mocks for all supported `/api/admin/users` and `/api/admin/configs/mail` operations.

#### Scenario: Admin API is consumed

- **WHEN** an admin page initiates a supported operation
- **THEN** the API module and mock SHALL use the documented request and response contract
