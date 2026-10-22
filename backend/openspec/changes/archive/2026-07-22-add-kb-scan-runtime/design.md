## Context

根目录已有独立 `tools/kb-scanner`，其 CLI 支持：

```text
python -m kb_scanner scan --input <source> --rules <ruleset> --output <out> --format json,html
```

扫描器输出固定文件：

- `scan-result.json`：机器可读结果，包含 `schemaVersion`、`tool`、`rulePack`、`project`、`summary`、`findings` 和 `diagnostics`。
- `scan-report.html`：供人工查看的 HTML 报告。
- `scan.log`：扫描诊断日志。

后端已经有项目、源码版本、任务、队列、SSE、任务日志、取消、`kb_scan_runs` 和 `findings` 表。缺口是 KB 扫描 API、worker handler、CLI 调用、结果导入、查询和测试。

## Goals / Non-Goals

**Goals:**

- 从项目源码版本创建 `KB_SCAN` 异步任务。
- 在 worker 中调用根目录 `tools/kb-scanner`，并登记本地进程以支持取消。
- 将 `scan-result.json` 中每条 finding 按行写入 `findings` 表。
- 将扫描摘要写入 `kb_scan_runs.summary`，并提供列表、详情、finding 查询 API。
- 通过项目级 SSE 和任务级日志 SSE 展示进度、日志和终态。
- 保存 HTML/log/JSON 输出的受控 artifact 或报告元数据，避免 API 暴露服务器真实路径。
- 测试覆盖正常流程、异常流程和 edge case。

**Non-Goals:**

- 不实现 `POST /api/kb-scans/{scanId}/findings:add-to-issues` 的问题清单联动。
- 不修改 `tools/kb-scanner` 的核心扫描规则和语言前端。
- 不把 KB Scanner 作为 Java 内部库嵌入。
- 不实现 AI 扩展知识库结果或纯 AI 扫描。

## Decisions

### 1. KB Scanner 作为独立 CLI 运行

后端通过受控本地进程调用 `tools/kb-scanner`，保持扫描器和平台解耦。这样与 SBOM Analyzer 的模式一致，后续扫描器独立升级时不需要重新设计 Java 模块边界。

替代方案是把 Python scanner 嵌入 Java 调用或改写成 Java 库。该方案会耦合工具生命周期、依赖管理和错误边界，不适合作为 MVP 后端集成路径。

### 2. 创建扫描时默认使用 active source revision

请求允许提交 `sourceRevisionId`；如果未提交，后端使用项目当前 active source revision。无论哪种方式，源码版本都必须属于 URL 中的 `projectId`，并且必须已有 `working_copy_path`。

这样前端可以简化默认流程，也允许用户对历史源码版本重新扫描。

### 3. Findings 按行入库，报告作为受控 artifact/元数据

`findings` 是事实表，必须支持分页、过滤和排序，因此不能把整个 `scan-result.json` 存成一个大 JSON 后再查。每条 finding 写入一行：

- `rule_id` 来自 finding `rule_id`
- `category` 优先来自 `finding_type` 或规则类别
- `severity` 来自 finding `severity`
- `title`、`description`、`suggestion` 来自 scanner 输出
- `file_path` 使用相对源码根路径
- `line_start`/`line_end` 来自 location
- `symbol` 来自 finding `symbol`
- `evidence` 保存受控 evidence、confidence、snippet、trace、condition macros、build context、scanner finding id 等
- `fingerprint` 使用 scanner finding id 或后端基于项目、源码版本、规则、位置、符号生成稳定 hash
- `status=DETECTED`

HTML 报告、JSON 摘要和 scan.log 不通过通用任务 artifact API 暴露。若当前 schema 不足，应新增 `kb_scan_artifacts` 存储轻量 metadata 和受控内容入口；API 不返回服务器真实路径。

### 4. Finding 代码上下文由后端按需读取

前端需要查看每个 finding 的源码上下文并高亮命中行，因此 `GET /api/findings/{findingId}` 返回 finding 事实详情和代码上下文摘要，另提供 `GET /api/findings/{findingId}/code-context` 返回完整上下文。

代码上下文不建议在扫描时完整入库。原因是源码片段数量可能很大。MVP 固定返回命中代码上 20 行和下 20 行；如果文件开头或结尾不足 20 行，则有多少返回多少。后端应在查询时根据：

```text
finding.source_revision_id
  -> source_revisions.working_copy_path
finding.file_path
  -> 工作副本内相对路径
finding.line_start / line_end
  -> 高亮范围
固定 contextBefore/contextAfter
  -> 20 / 20
```

读取源码文件并返回：

- `filePath`：相对路径
- `startLine` / `endLine`：实际返回的上下文范围
- `highlightStartLine` / `highlightEndLine`：需要前端高亮的命中范围
- `contextBefore=20` / `contextAfter=20`
- `lines[]`：`lineNumber`、`text`、`highlighted`

安全边界：

- `file_path` 必须 normalize 后仍位于 `working_copy_path` 内。
- 不允许客户端提交任意路径，只能使用 finding 已保存的相对路径。
- 不返回 `working_copy_path` 或服务器真实绝对路径。
- 上下文行数固定为上 20 行、下 20 行，避免一次读取超大文件。
- MVP 不开放 `before` / `after` 参数；后续如需自定义上下文范围应另行设计。

### 5. 任务生命周期由 `tasks` 和 `kb_scan_runs` 双写表达

`tasks.status` 是通用任务事实；`kb_scan_runs.status` 是 KB 扫描领域运行状态。创建时：

1. 创建 `tasks(KB_SCAN, PENDING)`。
2. 创建 `kb_scan_runs(PENDING)` 绑定 `task_id`。
3. 事务提交后投递队列并进入 `QUEUED`。

worker 执行时同步更新 `kb_scan_runs`：

```text
QUEUED/RUNNING -> SUCCEEDED
               -> FAILED
               -> CANCELLED
               -> TIMEOUT
```

### 6. CLI 输出目录使用后端 runtime 受控目录

每次扫描使用独立输出目录，建议绑定 `projectId/taskId/scanRunId`。后端只在数据库中保存受控引用、摘要、hash、大小和 artifact 类型，API 不返回绝对路径。

### 7. 日志和 SSE 复用现有任务运行时

worker 将 scanner stdout/stderr 写入任务日志和任务级日志事件；阶段进度建议：

```text
0   任务创建
10  校验源码版本和规则集
20  准备输出目录
30  启动 KB Scanner
70  Scanner 执行完成
85  解析 scan-result.json
95  findings 入库和 artifact 记录
100 完成
```

项目级 SSE 用于任务状态；任务级日志 SSE 用于 scanner 输出恢复。

## Risks / Trade-offs

- Scanner 输出 schema 变化 → 后端解析器必须校验 `schemaVersion`，不兼容时任务失败并保留安全错误摘要。
- 源码工作副本不存在或被清理 → 创建扫描时拒绝，避免 worker 才失败。
- finding 数量较大 → 必须批量插入，并为 `scan_run_id`、`project_id,severity`、`source_revision_id`、`file_path`、`fingerprint` 建索引。
- HTML 报告较大 → 默认不在列表接口返回内容；只保存 metadata 和受控下载/查看入口。
- scanner 运行时间长 → 需要配置超时，并将本地进程登记到 runtime handle，取消任务时可终止进程。
- 服务器路径泄露 → API 响应、task event、log excerpt、artifact summary 统一脱敏，不返回 `working_copy_path`、output dir 或完整命令。
