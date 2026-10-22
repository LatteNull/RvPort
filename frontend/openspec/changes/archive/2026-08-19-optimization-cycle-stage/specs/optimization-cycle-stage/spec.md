## ADDED Requirements

### Requirement: Optimization cycle overview

The system SHALL expose the optimization-closure workflow node and show the current backend optimization cycle for the selected project.

#### Scenario: Current cycle is available

- **WHEN** a user opens the optimization-closure node for a project with an active optimization cycle
- **THEN** the Drawer shows the cycle number, source revision, status, and available stage summaries

#### Scenario: Current cycle is unavailable

- **WHEN** a user opens the optimization-closure node for a project without an optimization cycle
- **THEN** the Drawer explains that a source revision must be imported or activated before optimization results can be summarized

### Requirement: Optimization cycle history and detail

The system SHALL provide a server-paginated list of optimization cycles and an in-Drawer detail view for a selected cycle.

#### Scenario: User filters or pages cycle history

- **WHEN** a user changes a supported history filter or page
- **THEN** the system requests and displays the corresponding server page

#### Scenario: User opens a cycle detail

- **WHEN** a user selects a cycle from the history list
- **THEN** the Drawer switches to that cycle's detailed stage summary without opening a nested overlay

### Requirement: Optimization stage navigation

The system SHALL provide navigation from optimization summaries to executable downstream stages without creating optimization tasks.

#### Scenario: User needs another build or test run

- **WHEN** a cycle summary shows missing or unsuccessful build or test results
- **THEN** the Drawer provides navigation to the relevant existing validation stage

#### Scenario: User is ready to deliver

- **WHEN** a cycle summary has the information needed for delivery review
- **THEN** the Drawer provides navigation to the archive stage
