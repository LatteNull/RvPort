--liquibase formatted sql

--changeset rvport:0020-projects
CREATE TABLE projects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    description text,
    source_arch text NOT NULL DEFAULT 'x86_64',
    target_arch text NOT NULL DEFAULT 'riscv64',
    stage text NOT NULL,
    status text NOT NULL,
    created_by uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz,
    deleted_at timestamptz,
    CONSTRAINT projects_stage_chk CHECK (stage IN (
        'PROJECT_CREATED',
        'SOURCE_IMPORTED',
        'ENV_CONFIGURED',
        'SCANNING',
        'REPORT_GENERATED',
        'WAITING_FIX',
        'BUILD_PASSED',
        'BUILD_FAILED',
        'TEST_PASSED',
        'TEST_FAILED',
        'ARCHIVED'
    )),
    CONSTRAINT projects_status_chk CHECK (status IN ('ACTIVE', 'ARCHIVED'))
);

CREATE INDEX projects_created_by_idx ON projects (created_by);
CREATE INDEX projects_stage_idx ON projects (stage);
CREATE INDEX projects_status_idx ON projects (status);
CREATE INDEX projects_updated_at_idx ON projects (updated_at DESC);

--changeset rvport:0021-source-revisions
CREATE TABLE source_revisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    revision_type text NOT NULL,
    version_label text,
    source_uri text,
    git_url text,
    git_branch text,
    git_commit text,
    archive_path text,
    working_copy_path text,
    version_note text,
    is_active boolean NOT NULL DEFAULT false,
    created_by uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT source_revisions_revision_type_chk CHECK (revision_type IN ('ARCHIVE', 'GIT'))
);

CREATE INDEX source_revisions_project_created_idx ON source_revisions (project_id, created_at DESC);
CREATE INDEX source_revisions_project_active_idx ON source_revisions (project_id, is_active);
CREATE INDEX source_revisions_project_commit_idx ON source_revisions (project_id, git_commit);
CREATE UNIQUE INDEX source_revisions_one_active_uidx ON source_revisions (project_id) WHERE is_active = true;

--changeset rvport:0022-source-imports
CREATE TABLE source_imports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    source_revision_id uuid REFERENCES source_revisions(id),
    task_id uuid,
    input_type text NOT NULL,
    status text NOT NULL,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT source_imports_input_type_chk CHECK (input_type IN ('ARCHIVE', 'GIT')),
    CONSTRAINT source_imports_status_chk CHECK (status IN ('PENDING', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT'))
);

CREATE INDEX source_imports_project_created_idx ON source_imports (project_id, created_at DESC);
CREATE INDEX source_imports_task_idx ON source_imports (task_id);
