## ADDED Requirements

### Requirement: Project list home page

The frontend SHALL render `/home` as the project list page for authenticated users.

#### Scenario: Authenticated user opens home

- **WHEN** an authenticated user opens `/home`
- **THEN** the page SHALL show the project list title, helper text, new-project button and project card grid

#### Scenario: Home follows design reference

- **WHEN** the project list page renders on a desktop viewport
- **THEN** the page SHALL visually follow `public/首页@2x.png` for header spacing, card density, risk badge placement, stage strip, status fields and card hover or active state

#### Scenario: Home renders on a wide viewport

- **WHEN** the project list page renders on a wide desktop viewport
- **THEN** the page SHALL keep the Figma card width and constrain the content area to reduce excessive right-side whitespace

### Requirement: Project list data loading

The frontend SHALL load project list data through a project API boundary using TanStack Query.

#### Scenario: Project list request starts

- **WHEN** `/home` needs project data
- **THEN** the page SHALL use a TanStack Query query that calls the project list API boundary

#### Scenario: Development mock serves projects

- **WHEN** the Vite dev server runs in serve mode and `/api/projects` is requested
- **THEN** the mock API SHALL return project list data using the current frontend response envelope

#### Scenario: Development mock supports scroll review

- **WHEN** developers review `/home` with the Vite mock API
- **THEN** the mock project list SHALL contain enough varied projects to exercise multi-row layout, page scrolling, long names and final-row rendering

#### Scenario: Project list request is loading

- **WHEN** the project list query is loading
- **THEN** the card area SHALL show skeleton-style loading content rather than a full-page spinner

#### Scenario: Project list request fails

- **WHEN** the project list query fails
- **THEN** the page SHALL show an error state with a retry action

#### Scenario: Project list is empty

- **WHEN** the project list query succeeds with no projects
- **THEN** the page SHALL show an empty state in the list area

### Requirement: Project card fields

The project card SHALL present MVP project-list fields from the product interaction specification.

#### Scenario: Project card renders normal project

- **WHEN** a project item is rendered
- **THEN** the card SHALL show project name, source architecture, target architecture, current stage, high-risk count, latest scan time, latest build status and latest test status

#### Scenario: Target architecture is displayed

- **WHEN** a project item has target architecture `riscv64`
- **THEN** the card SHALL display it as `RISC-V`

#### Scenario: Missing project status value

- **WHEN** scan time, build status or test status is missing
- **THEN** the corresponding field SHALL show a neutral placeholder

### Requirement: Project card interactions

The project list page SHALL provide visual interaction states without implementing project detail or creation flows.

#### Scenario: User hovers a project card

- **WHEN** the user hovers or focuses a project card
- **THEN** the card SHALL show a clear interactive visual state consistent with the design reference

#### Scenario: User sees new-project button

- **WHEN** the project list page renders
- **THEN** the page SHALL show a new-project button without opening a creation modal in this change

#### Scenario: User sees report affordance

- **WHEN** a project item has report available
- **THEN** the card SHALL expose report-oriented text or affordance without navigating to a report page in this change

### Requirement: Project list scope control

The project list home page SHALL remain limited to project list display for this change.

#### Scenario: Change scope is reviewed

- **WHEN** reviewers inspect this change
- **THEN** new project creation, project detail, migration pipeline navigation, report page navigation and US18 dashboard features SHALL be out of scope
