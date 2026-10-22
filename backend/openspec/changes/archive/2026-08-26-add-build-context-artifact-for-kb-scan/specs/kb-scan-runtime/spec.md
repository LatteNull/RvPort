## ADDED Requirements

### Requirement: KB 扫描必须自动复用构建上下文 compile database
KB 扫描运行时 SHALL 在执行 scanner 前自动查找同一项目和源码版本下最新成功 source/x86 构建保存的 compile database，并在可用时传给 KB Scanner。

#### Scenario: 自动使用最新成功构建上下文
- **WHEN** worker 执行 `KB_SCAN` 任务
- **AND** 同一 `projectId` 和 `sourceRevisionId` 存在最新成功 source/x86 构建
- **AND** 该构建的 `build_facts.compileDatabase.available=true`
- **THEN** worker SHALL 从对象存储下载对应 compile database 到受控临时文件
- **AND** worker SHALL 调用 KB Scanner 时传入 `--compile-commands <temp-file>`
- **AND** `kb_scan_runs.summary.compileCommands.mode` SHALL 为 `USED`
- **AND** summary SHALL 记录来源 build run ID、stored artifact ID、sha256 和 command count

#### Scenario: 没有构建上下文时降级扫描
- **WHEN** worker 执行 `KB_SCAN` 任务
- **AND** 同一源码版本不存在可用 compile database
- **THEN** worker SHALL 不传 `--compile-commands`
- **AND** KB Scanner SHALL 按源码上下文扫描继续执行
- **AND** `kb_scan_runs.summary.compileCommands.mode` SHALL 为 `NOT_AVAILABLE`
- **AND** summary SHALL 保存安全原因码

#### Scenario: artifact 下载失败时降级扫描
- **WHEN** worker 找到 compile database artifact 但对象存储下载失败或内容不可用
- **THEN** worker SHALL 记录 warning
- **AND** worker SHALL 不传 `--compile-commands`
- **AND** KB Scanner SHALL 按源码上下文扫描继续执行
- **AND** `kb_scan_runs.summary.compileCommands.mode` SHALL 为 `FALLBACK`

#### Scenario: 源码版本隔离
- **WHEN** 项目上传或同步新源码并产生新的 `source_revision_id`
- **THEN** KB 扫描 MUST NOT 复用旧源码版本的 compile database
- **AND** 后端 SHALL 只查询与本次 scan run 相同 `source_revision_id` 的构建上下文

#### Scenario: 扫描输出继续脱敏
- **WHEN** KB Scanner 使用 compile database 产生 findings、diagnostics、stdout、stderr 或 artifacts
- **THEN** 后端 SHALL 继续执行现有路径脱敏和输出安全处理
- **AND** API、SSE 和 artifact summary MUST NOT 暴露 compile database 临时路径、远端路径或对象存储 key
