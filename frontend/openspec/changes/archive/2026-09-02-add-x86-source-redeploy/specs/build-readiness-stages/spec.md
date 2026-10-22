## MODIFIED Requirements

### Requirement: Source-only x86 build

The system SHALL provide an x86 build stage that creates build runs only with `SOURCE_ONLY` scope against the project-level source environment and the active source revision.

#### Scenario: Create a source-only x86 build

- **WHEN** a user provides a valid build command, working directory, timeout, and optional environment variables while the active source revision and its source deployment are available
- **THEN** the system SHALL create a `SOURCE_ONLY` build run and show its task status, logs, and configuration in the x86 build stage

#### Scenario: Source deployment is unavailable

- **WHEN** the active source revision has no successful current source deployment in the project-level source environment
- **THEN** the system SHALL prevent creation of the x86 build and provide the existing “部署当前源码” recovery action

#### Scenario: Redeploy the current source

- **WHEN** the active source revision has a successful source deployment and the user confirms “重新部署” from the x86 build prerequisite panel
- **THEN** the system SHALL create a source deployment task for the active source revision with `force: true`
- **AND** SHALL show the operation progress and refresh the current deployment and project overview caches after task creation
