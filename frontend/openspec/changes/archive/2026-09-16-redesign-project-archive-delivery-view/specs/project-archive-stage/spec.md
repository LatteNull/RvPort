## MODIFIED Requirements

### Requirement: Project archive overview

The system SHALL expose the archive workflow node and display the latest archive state for the selected project. The overview SHALL prioritize delivery readiness, source revision, item count, package size, generated time, and the primary package action. Integrity identifiers and checksums SHALL remain available through an expandable traceability section with copy actions.

#### Scenario: Latest archive exists

- **WHEN** a user opens the archive node for a project with an archive snapshot
- **THEN** the Drawer shows its delivery conclusion, source revision, status, item count, package size, generated time, and available primary action
- **AND** the user can expand traceability information to copy its checksum and related record identifiers

#### Scenario: No archive exists

- **WHEN** a user opens the archive node for a project without an archive snapshot
- **THEN** the Drawer shows an empty state and the action to create an archive when a current source revision is available

### Requirement: Archive history, detail, and download

The system SHALL provide server-paginated archive history, in-Drawer archive detail, and downloads supported by the backend. Archive items SHALL use business-facing Chinese stage and content labels, expose technical metadata progressively, and group available formats behind one item download action.

#### Scenario: User reviews archive history

- **WHEN** a user changes an archive history filter or page
- **THEN** the system requests and displays the corresponding server page
- **AND** each record prioritizes source revision, delivery count and formats, package size, status, and generated time

#### Scenario: User opens archive detail

- **WHEN** a user selects an archive record
- **THEN** the Drawer displays its collected archive items without opening a nested overlay
- **AND** technical item metadata remains collapsed until the user requests it

#### Scenario: User downloads an archive artifact

- **WHEN** a user chooses an available archive package or selects an item format from its download menu
- **THEN** the system starts the corresponding backend download
