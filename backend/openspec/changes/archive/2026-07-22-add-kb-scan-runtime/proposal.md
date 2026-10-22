## Why

当前仓库已经包含独立 `tools/kb-scanner`，数据库和 API 文档也预留了 KB 扫描模型，但 Java 后端尚不能从项目源码版本发起扫描、运行 CLI、解析结果并向前端提供可查询的 finding。需要把 KB 扫描接入现有任务、队列、SSE 和源码版本体系，形成可用的知识库扫描闭环。

## What Changes

- 增加 `KB_SCAN` 任务创建、投递、worker 处理和取消能力。
- 增加 KB 扫描 API：创建扫描、查询扫描列表、查询扫描详情、分页查询 findings、查询 finding 详情。
- 后端调用根目录 `tools/kb-scanner` 作为独立 CLI，不把 scanner 作为 Java 内部库嵌入。
- 解析 `scan-result.json`，将每条 finding 按行写入 `findings`，并更新 `kb_scan_runs` 摘要和状态。
- 保存 KB 扫描输出的 JSON/HTML/log 摘要或 artifact 元数据，用于后续审计和报告入口。
- 扫描任务通过项目级 SSE 和任务日志 SSE 返回进度、日志和终态。
- 补充正常流程、异常流程和 edge case 的单元测试、轻量集成测试和 E2E 模块测试。
- 本 change 不实现 `findings:add-to-issues` 的问题清单联动。

## Capabilities

### New Capabilities

- `kb-scan-runtime`: 定义 KB Scanner 后端运行时、结果导入、artifact 管理、任务生命周期和测试要求。

### Modified Capabilities

- `backend-api-design`: 增加并细化 KB 扫描 API 的请求、响应、权限、分页、过滤、排序和非实现范围。
- `backend-database-design`: 补充 KB 扫描运行、finding 和 artifact/报告元数据的字段、索引、状态与敏感信息要求。
- `task-runtime`: 增加 `KB_SCAN` 任务类型、队列执行、SSE 事件和取消语义。
- `project-source-environment`: 明确 KB 扫描基于后端本机源码工作副本执行，并校验源码版本属于当前项目。
- `api-e2e-test-suite`: 增加 KB 扫描模块化 E2E，覆盖创建、执行、查询和清理。

## Impact

- 后端 Java 包：新增 `kb` API/service/repository/runtime/DTO/test。
- 任务系统：新增 `RvPortTaskTypes.KB_SCAN` 和 `TaskHandler`。
- 数据库：可能新增 KB artifact 表或补充 `kb_scan_runs.summary`/metadata 存储约定。
- 工具调用：通过受控进程调用 `tools/kb-scanner`，需要配置 Python 命令、scanner 路径、规则集路径、输出目录和超时。
- 安全：API 不返回服务器真实路径、源码工作副本路径、完整 scanner stdout/stderr 或敏感路径。
- 测试：新增 Java 单元测试、scanner 输出解析测试、E2E 模块测试。
