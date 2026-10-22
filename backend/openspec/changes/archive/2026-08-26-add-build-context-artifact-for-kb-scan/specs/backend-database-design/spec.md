## ADDED Requirements

### Requirement: 数据库必须支持构建上下文 artifact 引用
数据库 SHALL 支持构建运行保存 compile database 输出制品引用，并 SHALL 支持 KB 扫描按项目和源码版本查询最新可用构建上下文。

#### Scenario: 构建运行保存 compile database 摘要
- **WHEN** 构建验证成功并发现可用 `compile_commands.json`
- **THEN** `build_runs.build_facts` SHALL 保存 compile database 的可用状态、stored artifact ID、sha256、size bytes、command count、来源环境、构建范围和来源摘要
- **AND** `build_facts` MUST NOT 保存完整 `compile_commands.json`、对象存储 key、服务器真实路径或远端绝对路径

#### Scenario: stored artifacts 支持构建归属
- **WHEN** 数据库维护 `stored_artifacts.owner_type` 约束
- **THEN** `owner_type` SHALL 支持 `BUILD_VALIDATION`
- **AND** `owner_id` SHALL 能引用对应业务 owner 的 ID
- **AND** 构建上下文 artifact SHALL 使用 `build_runs.id` 作为 owner ID

#### Scenario: 查询最新可用构建上下文
- **WHEN** KB 扫描需要按项目和源码版本查询最新成功构建上下文
- **THEN** 数据库 SHALL 支持按 `project_id`、`source_revision_id`、`build_scope`、`status` 和完成时间查询 `build_runs`
- **AND** 查询 SHALL 能过滤或识别 `build_facts.compileDatabase.available=true` 的记录
- **AND** 查询 MUST NOT 依赖跨源码版本的最近构建记录

#### Scenario: 对象存储元数据安全
- **WHEN** 保存构建上下文 artifact 元数据
- **THEN** `stored_artifacts.summary` MUST NOT 保存完整日志、完整 compile database、明文凭据、服务器真实路径、远端工作目录、bucket 或 object key
