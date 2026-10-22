## ADDED Requirements

### Requirement: Source-only x86 build

The system SHALL provide an x86 build stage that creates build runs only with `SOURCE_ONLY` scope against the project-level source environment and the active source revision.

#### Scenario: Create a source-only x86 build

- **WHEN** a user provides a valid build command, working directory, timeout, and optional environment variables while the active source revision and its source deployment are available
- **THEN** the system SHALL create a `SOURCE_ONLY` build run and show its task status, logs, and configuration in the x86 build stage

#### Scenario: Source deployment is unavailable

- **WHEN** the active source revision has no successful current source deployment in the project-level source environment
- **THEN** the system SHALL prevent creation of the x86 build and guide the user to the source management workflow

### Requirement: x86 build history and currentness

The system SHALL show server-paginated x86 build history for the project and distinguish a record that is no longer associated with the active source revision or current runtime-environment configuration.

#### Scenario: Review an x86 build record

- **WHEN** a user opens an x86 build history record
- **THEN** the system SHALL show its source revision, source environment, command, working directory, status, timestamps, exit code, and available logs

#### Scenario: Source or environment configuration changes

- **WHEN** an x86 build record does not match the active source revision or current runtime-environment configuration
- **THEN** the system SHALL mark the record as non-current and SHALL NOT present it as the current build prerequisite

### Requirement: Dependency analysis from current x86 build

The system SHALL provide a dependency analysis stage that consumes the current source revision's successful x86 `SOURCE_ONLY` build and compares its dependencies against the project-level RISC-V target environment.

#### Scenario: Start dependency analysis

- **WHEN** the active source revision has a successful current x86 `SOURCE_ONLY` build and project-level runtime environments are complete
- **THEN** the system SHALL allow the user to create a dependency analysis and SHALL show the source revision, source build, and target environment as read-only analysis inputs

#### Scenario: No usable x86 build exists

- **WHEN** no successful current x86 `SOURCE_ONLY` build exists for the active source revision
- **THEN** the system SHALL prevent dependency analysis creation and guide the user to the x86 build stage

### Requirement: Dependency analysis results and history

The system SHALL show server-paginated dependency analysis history and result items with filtering, record detail, and access to analysis artifacts returned by the backend.

#### Scenario: Inspect dependency results

- **WHEN** a user opens a completed dependency analysis
- **THEN** the system SHALL display dependency type, name, version, target match status, risk level, source location, recommendation, and confidence for each result item

#### Scenario: Inspect analysis evidence

- **WHEN** a user opens a dependency result item
- **THEN** the system SHALL display the backend-provided evidence and recommendation without synthesizing replacement data on the client

### Requirement: Manual status refresh

The system SHALL refresh x86 build and dependency analysis records only through explicit user action and SHALL NOT poll these task endpoints.

#### Scenario: Refresh a running record

- **WHEN** a user refreshes a stage with a running build or dependency analysis
- **THEN** the system SHALL reload the current stage summary, history, and active detail from the backend
