## ADDED Requirements

### Requirement: 项目表必须保存源码来源锁定字段
数据库 SHALL 在 `projects` 表保存项目级源码来源锁定状态，用于约束后续源码入库方式。

#### Scenario: 创建源码来源锁定字段
- **WHEN** 执行数据库迁移
- **THEN** Schema SHALL 在 `projects` 表增加 `source_input_type text nullable`
- **AND** `source_input_type` SHALL 只允许 `ARCHIVE`、`GIT` 或 `null`
- **AND** `null` SHALL 表示项目尚未成功入库源码

#### Scenario: 回填已有项目源码来源
- **WHEN** 数据库中已有项目存在源码版本
- **THEN** 迁移 SHALL 根据该项目当前 active 源码版本的 `revision_type` 回填 `source_input_type`
- **AND** 如果没有 active 源码版本但存在历史源码版本，迁移 SHALL 根据最早成功源码版本的 `revision_type` 回填
- **AND** 如果项目没有源码版本，`source_input_type` SHALL 保持 `null`

#### Scenario: 混合历史源码来源处理
- **WHEN** 历史项目同时存在 `ARCHIVE` 和 `GIT` 源码版本
- **THEN** 迁移 SHALL 使用 active 源码版本的 `revision_type` 作为锁定来源
- **AND** 如果没有 active 源码版本，迁移 SHALL 使用最早成功源码版本的 `revision_type`
- **AND** 后续业务请求 SHALL 按回填后的锁定来源执行校验

#### Scenario: 源码版本保存工作副本路径
- **WHEN** 创建或维护 `source_revisions` 表
- **THEN** `working_copy_path` SHALL 用于保存压缩包解包目录或 Git checkout 工作副本目录
- **AND** `archive_path` SHALL 只保存原始上传包路径
- **AND** API 响应、任务事件和审计摘要 MUST NOT 暴露这两个服务器本地路径

#### Scenario: 索引源码来源查询路径
- **WHEN** 后端查询项目列表、项目详情或校验源码入库方式
- **THEN** 数据库 SHALL 支持高效读取 `projects.source_input_type`
- **AND** 如实现需要按源码来源筛选项目，数据库 MAY 为 `source_input_type` 建立索引
