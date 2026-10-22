## ADDED Requirements

### Requirement: Create project modal

The frontend SHALL allow authenticated users to create a migration project from the home page using a modal dialog.

#### Scenario: User opens create project modal

- **WHEN** an authenticated user clicks the `+ 新建` button on `/home`
- **THEN** the frontend SHALL open a create project modal without navigating away from the project list page

#### Scenario: User cancels create project

- **WHEN** the create project modal is open and the user cancels or closes it
- **THEN** the frontend SHALL close the modal without creating a project or changing the project list data

### Requirement: Shared business modal shell

The frontend SHALL provide a reusable business modal shell for modal dialogs that visually differ from the default Ant Design Modal.

#### Scenario: Business modal renders

- **WHEN** a business modal is displayed
- **THEN** it SHALL use Ant Design Modal behavior while applying the project modal visual conventions for header, body spacing, footer actions, default width, close affordance and mask presentation

#### Scenario: Business modal width is overridden

- **WHEN** a feature passes a modal width to the shared business modal shell
- **THEN** the shell SHALL pass that width through to Ant Design Modal instead of forcing a single global width

#### Scenario: Business modal remains generic

- **WHEN** a feature uses the shared business modal shell
- **THEN** the shell SHALL NOT contain project-specific form fields, API calls or query invalidation logic

### Requirement: Create project form

The create project modal SHALL collect MVP project creation fields.

#### Scenario: Create project form opens with defaults

- **WHEN** the create project modal opens
- **THEN** the form SHALL show empty project name and description fields, source architecture defaulted to `x86_64`, target architecture defaulted to `riscv64`, and source input type defaulted to later import from source management

#### Scenario: Create project form follows modal design

- **WHEN** the create project modal renders on a desktop viewport
- **THEN** the modal SHALL follow Figma node `14:296` with an 800px modal width, single-column fields, section titles and a footer action row

#### Scenario: Create project modal content overflows

- **WHEN** the create project modal is open and content exceeds the available viewport height
- **THEN** scrolling SHALL occur inside the modal body while the page content behind the modal remains locked

#### Scenario: Required project name is missing

- **WHEN** the user submits the create project form without a project name
- **THEN** the frontend SHALL block submission and show a field validation message

#### Scenario: Source input type is selected

- **WHEN** the user chooses a source input type
- **THEN** the form SHALL capture the selected source input type for the create project request without uploading source files or pulling Git code in this change

#### Scenario: Save and enter environment management is clicked

- **WHEN** the user clicks the save-and-enter-environment action in this change
- **THEN** the frontend SHALL create the project with the same submit behavior as save without navigating to environment management

### Requirement: Create project API integration

The frontend SHALL create projects through the project API boundary using the formal API response envelope.

#### Scenario: User submits valid project form

- **WHEN** the user submits a valid create project form
- **THEN** the frontend SHALL call `POST /projects` through the project API boundary with name, description, source architecture, target architecture and source input type

#### Scenario: Project creation succeeds

- **WHEN** `POST /projects` succeeds
- **THEN** the frontend SHALL close the modal, show success feedback and refresh the home project list query

#### Scenario: Project creation fails

- **WHEN** `POST /projects` fails
- **THEN** the frontend SHALL keep the modal open, stop the submitting state and show an error message

#### Scenario: Development mock creates project

- **WHEN** the Vite dev server runs in serve mode and `/api/projects` receives a valid create request
- **THEN** the mock API SHALL return a created project using the formal `success/data/error/traceId/timestamp` response envelope

### Requirement: Create project scope control

The create project change SHALL remain limited to creating the project context.

#### Scenario: Change scope is reviewed

- **WHEN** reviewers inspect this change
- **THEN** source archive upload, Git repository synchronization, project detail navigation, environment management and migration pipeline execution SHALL be out of scope
