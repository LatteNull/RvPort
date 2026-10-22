## Why

KB Scanner 已完成 schema v2 重构并将默认输出切换为 `schemaVersion: "2.0"`，但后端仍按旧的 v1 扁平 DTO 解析，并在运行时拒绝 v2 结果。现在需要让后端构建、运行、入库和 API 全面接入新的 Finding-centric schema，避免前后端继续围绕旧合同扩展。

## What Changes

- **BREAKING** 后端 KB 扫描结果解析从 schema v1 切换到 schema v2，默认不再兼容 v1 扁平 Finding DTO。
- **BREAKING** KB finding 列表和详情 API 将以 schema v2 的 `fact`、`conclusion`、`occurrences`、`evidenceChain` 为主结构返回；现有旧字段只作为必要的索引/摘要投影保留。
- 后端 Docker 镜像安装新 KB Scanner 所需的 Python runtime 依赖、`clang-18`、`libclang-18-dev` 和 `python3-clang-18`，并使用隔离的 Python venv 执行 scanner。
- KB 扫描任务显式以 `--schema-version 2.0` 调用 scanner，只接受 v2 artifact，并保存 `scan-result.json`、`scan-report.html`、`scan.log` 三类 artifact 的 v2 版本信息。
- 后端将 v2 finding 逐条投影入 `findings` 表，保留分页、排序、过滤、报告纳入状态、迁移输入引用和 AI 扩展所需的可查询字段。
- Finding 详情返回完整 v2 finding payload，代码上下文接口继续提供后端读取源码得到的前后文展示能力，并与 v2 primary location 对齐。
- 更新单元测试和 E2E，覆盖 schema v2 正常导入、异常版本拒绝、缺失位置/上下文等 edge case，以及真实 KB Scanner v2 运行链路。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `kb-scan-runtime`: KB 扫描运行时、结果导入、artifact 保存和 finding 查询切换到 schema v2。
- `backend-api-design`: KB finding 相关 API 的响应结构改为 schema v2 优先。
- `backend-infrastructure`: 后端生产镜像需要安装并隔离运行新 KB Scanner 所需的 Python/Clang 依赖。
- `api-e2e-test-suite`: E2E 需要覆盖真实 schema v2 scanner 输出、artifact 下载和 finding 详情查询。
- `kb-ai-extension-runtime`: AI 扩展输入需要读取 v2 finding 结构与源码上下文，不再依赖 v1 trace/扁平字段。

## Impact

- 影响后端 Dockerfile、Compose 环境变量、KB 扫描运行服务、scanner 结果 DTO、finding 入库 mapper、finding API response、代码上下文查询、KB AI 扩展输入导出、迁移输入来源解析、报告输入预览和相关测试。
- 后端镜像体积会增加，主要来自 Clang/libclang 与 Python scanner runtime 依赖。
- 旧 schema v1 扫描结果不再作为默认运行合同；历史已入库 finding 可继续按数据库现有字段读取，但新任务只产生 v2 artifact 和 v2 evidence。
