## MODIFIED Requirements

### Requirement: KB 扫描运行表必须支持异步任务和摘要查询
数据库 SHALL 使用 `kb_scan_runs` 保存 KB 扫描运行事实，支持按项目、源码、执行上下文和状态查询，并持久化新扫描所绑定的 x86 构建身份。

#### Scenario: 创建 KB 扫描运行
- **WHEN** 后端创建 KB 扫描任务
- **THEN** 数据库 SHALL 保存 `kb_scan_runs` 记录
- **AND** `project_id` SHALL 关联项目
- **AND** `task_id` SHALL 唯一关联 `tasks.id`
- **AND** `source_revision_id` SHALL 关联被扫描源码版本
- **AND** 新服务 SHALL 完整写入 `source_environment_id`、`runtime_environment_version` 和 `build_run_id`
- **AND** `build_run_id` SHALL 关联经服务验证与项目、源码、源环境、运行环境版本一致的成功 `SOURCE_ONLY` 构建
- **AND** `status` SHALL 使用 `PENDING`、`QUEUED`、`RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED` 或 `TIMEOUT`
- **AND** `scope` SHALL 保存扫描范围、排除路径、语言、目标架构和规则集摘要

#### Scenario: 更新运行摘要
- **WHEN** KB 扫描完成或失败
- **THEN** `kb_scan_runs.summary` SHALL 保存 schema version、tool version、rule pack、文件数、finding 数量、severity counts、diagnostics 摘要和 artifact 摘要
- **AND** compile database 降级时 SHALL 仍保存绑定构建身份及安全原因
- **AND** summary MUST NOT 保存源码工作副本路径、scanner 输出目录、明文凭据或完整 stdout/stderr
- **AND** 执行结果更新 MUST NOT 改写创建时绑定的执行上下文

#### Scenario: 查询 KB 扫描运行
- **WHEN** 创建或维护 `kb_scan_runs`
- **THEN** 数据库 SHALL 保留 `project_id, started_at desc` 和 `source_revision_id` 的既有索引
- **AND** 数据库 SHALL 提供支持项目、源码、源环境、运行环境版本和构建 ID 联合筛选的索引
- **AND** repository SHALL 在筛选有效上下文后执行活动优先、创建时间与 ID 稳定排序
- **AND** 计数查询与分页查询 SHALL 使用一致过滤条件

#### Scenario: 旧数据升级
- **WHEN** 数据库从没有扫描上下文列的版本升级
- **THEN** 迁移 SHALL 以可空字段保留旧行，并允许新增上下文全空或完整填写，拒绝部分填写
- **AND** 旧记录 SHALL 保留原状态、finding 和 artifact 关联
- **AND** 迁移 MUST NOT 根据当前环境或 summary 中不完整信息推测回填
- **AND** 新查询 SHALL 将上下文缺失的旧行判为历史，不能作为当前扫描

#### Scenario: 迁移与生成类型验证
- **WHEN** 实施数据库变更
- **THEN** SHALL 在独立 Docker 数据库验证空库初始化、旧数据升级、重复迁移、外键和上下文完整性约束
- **AND** SHALL 在容器内生成 jOOQ 类型并以当前源码完成编译与单元验证
- **AND** 迁移或代码生成验证 MUST NOT 替代业务单元测试和覆盖率门槛
