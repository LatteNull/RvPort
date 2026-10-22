# Backend database guide

English | [简体中文](DATABASE_DESIGN.zh-CN.md)

The database uses PostgreSQL. `src/main/resources/db/changelog/db.changelog-master.yaml` and its referenced SQL define the schema. Liquibase manages change order; jOOQ types are generated from an initialized database. Historical design records remain in backend OpenSpec.

## Main data domains

| Domain | Main data |
|---|---|
| Accounts and access | Users, invitation/reset tokens, system configuration, audit logs |
| Projects and source | Projects, source revisions, imports, deployments, project execution-environment bindings |
| Environments and credentials | Encrypted credentials, environments, snapshots, environment components |
| Tasks and workers | Tasks, events, logs, runtime handles, worker heartbeats |
| Migration analysis | KB scans/findings, build-driven dependency analysis, dependency remediation, floating-point and memory-order analysis |
| Migration inputs and issues | Input sets, source references, issues, issue events |
| Models and agents | Model configuration, stage assignments, agent runtimes, probe records |
| Builds and validation | Build runs, automated tests, test comparisons, differences |
| Reports and artifacts | Reports, report inputs, object-storage artifacts, archive candidates, archive items |

## Data and execution boundaries

PostgreSQL holds the authoritative state of tasks and business results. RabbitMQ delivers task identifiers, and workers read inputs from the database. Object storage holds output artifacts; the database records their ownership and locations. Logs and credentials must follow the access and redaction rules of the corresponding services.

Credentials are encrypted with the deployment-provided master key before being written to the database. Never place that key in source, database migrations, or test reports. See the installation guide for default administrator initialization; development defaults must not be used as deployment credentials.

## Initialization and generated code

Initialize a fresh deployment with an empty database. Liquibase's change chain creates foreign keys, constraints, and indexes. Validate changeset checksums and data compatibility separately before upgrading an existing deployment.

Run all migration validation and jOOQ generation in Docker, using separate containers, networks, and databases rather than the running database. See the [development guide](../../docs/development.md).

Generated types are stored in `src/generated/java/`. Regenerate them after schema changes. Hand-editing types does not replace initialization and generation validation.
