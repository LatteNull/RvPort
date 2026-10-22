## MODIFIED Requirements

### Requirement: Project card interactions

The project list page SHALL provide visual interaction states and a creation entry point without implementing project detail, report navigation or pipeline navigation flows.

#### Scenario: User hovers a project card

- **WHEN** the user hovers or focuses a project card
- **THEN** the card SHALL show a clear interactive visual state consistent with the design reference

#### Scenario: User opens create project modal

- **WHEN** the user clicks the new-project button
- **THEN** the page SHALL open the create project modal

#### Scenario: User sees report affordance

- **WHEN** a project item has report available
- **THEN** the card SHALL expose report-oriented text or affordance without navigating to a report page in this change
