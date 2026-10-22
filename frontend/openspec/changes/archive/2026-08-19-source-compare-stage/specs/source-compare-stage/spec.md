## ADDED Requirements

### Requirement: Source comparison stage presents latest recheck context

The system SHALL provide a dedicated source comparison stage Drawer that loads the project's latest source comparison and identifies the current active source revision and the previous source revision.

#### Scenario: Comparison has two source revisions

- **WHEN** the project has an active source revision and a previous source revision
- **THEN** the Drawer SHALL display both revision summaries and the latest comparison status

#### Scenario: Active source revision is missing

- **WHEN** the latest comparison reports no active source revision
- **THEN** the Drawer SHALL explain that source management must import and activate a source revision before comparison

#### Scenario: Previous source revision is missing

- **WHEN** the latest comparison reports no previous source revision
- **THEN** the Drawer SHALL explain that a second source version is required and provide an entry to source management

### Requirement: Source comparison stage controls latest recheck

The system SHALL drive source comparison actions from the latest comparison status without asking the user to select arbitrary source revision IDs.

#### Scenario: Recheck has not started

- **WHEN** the latest comparison status is `NOT_STARTED`
- **THEN** the Drawer SHALL allow the user to create a latest recheck

#### Scenario: Recheck is running

- **WHEN** the latest comparison status is `RUNNING`
- **THEN** the Drawer SHALL present an in-progress state and refresh the latest comparison until it reaches a terminal state

#### Scenario: Recheck failed

- **WHEN** the latest comparison status is `FAILED`
- **THEN** the Drawer SHALL show the failure state and allow the user to retry the latest recheck

### Requirement: Source comparison stage displays diff summary and list

The system SHALL display successful recheck results as a status summary and a server-paginated difference list.

#### Scenario: Recheck succeeds

- **WHEN** the latest comparison status is `SUCCEEDED`
- **THEN** the Drawer SHALL display counts for resolved, unchanged, changed, and new differences

#### Scenario: User filters differences

- **WHEN** the user applies difference status, source type, severity, or match confidence filters
- **THEN** the system SHALL request and display the matching server-paginated difference items

#### Scenario: User opens a difference detail

- **WHEN** the user selects a difference item detail action
- **THEN** the Drawer SHALL switch to an in-Drawer detail view containing the item status, match information, and available old and new records

### Requirement: Successful source comparison leads to build validation

The system SHALL enable the transition to build validation only after a successful source comparison.

#### Scenario: User enters build validation after success

- **WHEN** the latest comparison status is `SUCCEEDED` and the user chooses to enter build validation
- **THEN** the system SHALL navigate to the build validation stage

### Requirement: Manual repair remains separate from source comparison

The system SHALL keep manual repair focused on offline repair guidance and source management navigation rather than rendering source comparison data.

#### Scenario: User opens manual repair

- **WHEN** the user opens the manual repair Drawer
- **THEN** the Drawer SHALL direct the user to update the repaired source through source management and SHALL NOT render latest comparison summary data

### Requirement: Workflow topology exposes source comparison

The system SHALL render source comparison as an active workflow node between manual repair and build validation.

#### Scenario: User views the workflow canvas

- **WHEN** the workflow canvas is rendered
- **THEN** it SHALL show the source repair group containing manual repair, a separate source comparison node, and edges from manual repair to source comparison and source comparison to build validation
