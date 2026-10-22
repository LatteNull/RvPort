## ADDED Requirements

### Requirement: Project archive overview

The system SHALL expose the archive workflow node and display the latest archive state for the selected project.

#### Scenario: Latest archive exists

- **WHEN** a user opens the archive node for a project with an archive snapshot
- **THEN** the Drawer shows its name, source revision, status, creation time, and available archive metadata

#### Scenario: No archive exists

- **WHEN** a user opens the archive node for a project without an archive snapshot
- **THEN** the Drawer shows an empty state and the action to create an archive when a current source revision is available

### Requirement: Create project archive

The system SHALL allow a user to create an archive task for the active project source revision after explicit confirmation.

#### Scenario: Archive creation succeeds

- **WHEN** a user confirms creation of the current project archive
- **THEN** the system creates the backend archive task and refreshes the archive overview and history

#### Scenario: No active source revision exists

- **WHEN** a user attempts to create an archive without an active source revision
- **THEN** the system prevents archive creation and directs the user to source management

### Requirement: Archive history, detail, and download

The system SHALL provide server-paginated archive history, in-Drawer archive detail, and downloads supported by the backend.

#### Scenario: User reviews archive history

- **WHEN** a user changes an archive history filter or page
- **THEN** the system requests and displays the corresponding server page

#### Scenario: User opens archive detail

- **WHEN** a user selects an archive record
- **THEN** the Drawer displays its collected archive items and metadata without opening a nested overlay

#### Scenario: User downloads an archive artifact

- **WHEN** a user chooses an available archive package or item format
- **THEN** the system starts the corresponding backend download
