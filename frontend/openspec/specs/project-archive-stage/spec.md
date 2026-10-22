## Purpose

定义项目归档节点的当前归档展示、需要明确确认的归档创建、历史追溯和安全下载操作的可观察前端行为与失败恢复路径。

## Requirements

### Requirement: Project archive overview

The system SHALL expose the archive workflow node and display the latest archive state for the selected project. The overview SHALL prioritize delivery readiness, source revision, item count, package size, generated time, and the primary package action. Integrity identifiers and checksums SHALL remain available through an expandable traceability section with copy actions.

#### Scenario: Latest archive exists

- **WHEN** a user opens the archive node for a project with an archive snapshot
- **THEN** the Drawer shows its delivery conclusion, source revision, status, item count, package size, generated time, and available primary action
- **AND** the user can expand traceability information to copy its checksum and related record identifiers

#### Scenario: No archive exists

- **WHEN** a user opens the archive node for a project without an archive snapshot
- **THEN** the Drawer shows an empty state and the action to create an archive when `ARCHIVE_CANDIDATES` readiness is satisfied

### Requirement: Create project archive

The system SHALL allow a user to create an archive task for the active project source revision after explicit confirmation.

#### Scenario: Archive creation succeeds

- **WHEN** a user confirms creation of the current project archive
- **THEN** the system SHALL 创建归档任务并提示已提交，由项目 SSE 刷新当前归档与历史

#### Scenario: No active source revision exists

- **WHEN** a user attempts to create an archive without an active source revision
- **THEN** the system prevents archive creation and directs the user to source management

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

### Requirement: 归档必须说明当前源码是否可交付

归档 SHALL 使用 `archive` readiness 的 `ARCHIVE_CANDIDATES` 作为唯一创建门禁，并使用 `archives/latest` 判断最近归档是否属于当前源码。

#### Scenario: 当前源码归档完成

- **WHEN** latest 为 `CURRENT`、归档成功且存在可下载产物
- **THEN** 页面 SHALL 展示交付结论、交付快照、完整性信息和交付清单
- **AND** Footer SHALL 以下载归档包作为唯一主操作

#### Scenario: 最近归档属于旧源码

- **WHEN** latest 为 `STALE`
- **THEN** 页面 SHALL 明确当前源码尚未归档
- **AND** 旧归档 SHALL 从历史入口读取与下载；当前概览的创建操作 SHALL 由 `ARCHIVE_CANDIDATES` readiness 决定，运行期间 SHALL 不提供再次执行入口
