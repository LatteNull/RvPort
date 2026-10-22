## ADDED Requirements

### Requirement: Backend API response envelope

The frontend SHALL model platform API responses using the currently implemented backend `data/traceId/timestamp` envelope.

#### Scenario: API response succeeds

- **WHEN** the backend returns a successful JSON API response
- **THEN** the response envelope SHALL contain `data`, `traceId` and `timestamp`
- **AND** the response envelope SHALL NOT require a `success` field

#### Scenario: API response fails

- **WHEN** the backend returns an API error response
- **THEN** the error body SHALL contain top-level `code`, `message`, optional `details`, `traceId` and `timestamp`
- **AND** the error body SHALL NOT require a nested `error` object

### Requirement: Backend pagination envelope

The frontend SHALL model paginated backend responses using the currently implemented backend `items/page/pageSize/total/hasMore` envelope.

#### Scenario: API response is paginated

- **WHEN** a backend API returns a paginated list
- **THEN** the frontend type SHALL expose `items`, `page`, `pageSize`, `total` and `hasMore`
- **AND** the frontend type SHALL NOT require a `list` field

### Requirement: Request client unwraps response data

The frontend request client SHALL return unwrapped response data to business API callers.

#### Scenario: Business API calls GET

- **WHEN** a business API calls `request.get<T>(...)`
- **THEN** TypeScript SHALL treat the returned promise as `Promise<T>`

#### Scenario: Business API calls POST

- **WHEN** a business API calls `request.post<T>(...)`
- **THEN** TypeScript SHALL treat the returned promise as `Promise<T>`

#### Scenario: Successful response is received

- **WHEN** the request client receives a successful API envelope
- **THEN** it SHALL resolve with the envelope `data`

### Requirement: Request client handles API errors

The frontend request client SHALL handle backend API errors consistently.

#### Scenario: Failed response is received

- **WHEN** the request client receives an HTTP error response with a backend API error body
- **THEN** it SHALL surface the top-level `message` and reject the request

#### Scenario: Unauthorized response is received

- **WHEN** an API request receives HTTP 401
- **THEN** the request client SHALL clear auth user state and move the user toward login

#### Scenario: Forbidden response is received

- **WHEN** an API request receives HTTP 403
- **THEN** the request client MAY refresh the current user through `/api/auth/me`
- **AND** it SHALL surface an authorization failure message

### Requirement: Request client uses Cookie Session and CSRF

The frontend request client SHALL align with the backend Cookie Session and CSRF model.

#### Scenario: API request is sent

- **WHEN** the request client sends API requests
- **THEN** it SHALL enable browser cookie credentials

#### Scenario: Unsafe method is sent

- **WHEN** the request client sends `POST`, `PUT`, `PATCH` or `DELETE`
- **THEN** it SHALL attach the CSRF token header returned by `GET /api/auth/csrf`

#### Scenario: Safe method is sent

- **WHEN** the request client sends `GET`, `HEAD` or `OPTIONS`
- **THEN** it SHALL NOT require a CSRF token before sending the request

#### Scenario: CSRF token is requested concurrently

- **WHEN** multiple unsafe API requests need a CSRF token at the same time
- **THEN** the request client SHALL reuse the in-flight CSRF request when possible
