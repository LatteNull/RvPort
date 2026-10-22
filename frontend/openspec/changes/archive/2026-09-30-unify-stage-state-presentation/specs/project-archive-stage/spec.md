## MODIFIED Requirements

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
