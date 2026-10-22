## Context

KB Scanner 已重构为 schema v2，并且默认输出 `schemaVersion: "2.0"`。后端当前仍按 schema v1 的扁平 DTO 读取 `scan-result.json`，并显式拒绝非 `1.0` 的结果；这会导致新的 scanner artifact 无法被运行、导入、分页查询、AI 扩展和报告流程消费。

后端 Docker 镜像当前只安装了 Python 基础环境和少量系统工具，缺少新版 KB Scanner 所需的 Python runtime 依赖、`clang-18`、`libclang-18-dev` 以及 Python Clang binding。用户已确认不需要默认兼容旧 v1 API/DTO，前端会后续按 schema v2 更新；本 change 只处理后端。

## Goals / Non-Goals

**Goals:**

- 后端生产镜像能够在隔离 Python venv 中运行新版 KB Scanner。
- KB 扫描任务显式使用 schema v2，并只接受 schema v2 结果。
- 后端导入 schema v2 finding，并保留完整 v2 payload 供详情、AI 扩展、报告和审计使用。
- KB finding 列表和详情 API 改为 v2 优先结构，同时保留必要的分页、排序、过滤和报告纳入状态。
- 更新单元测试与 E2E，覆盖正常流程、异常流程和 edge case。

**Non-Goals:**

- 不修改前端页面和前端 API 调用。
- 不继续默认兼容 schema v1 扫描结果。
- 不修改 KB Scanner 的输出文件格式。
- 不迁移历史 v1 artifact；历史已入库的 finding 只按现有数据库投影继续查询。
- 不改变 scanner 自身的上下文行数、规则语义和报告生成逻辑。

## Decisions

1. **后端镜像使用 Python venv 运行 scanner**

   使用 `python3 -m venv --system-site-packages` 创建隔离环境，并在 venv 中安装 `tools/kb-scanner/requirements/runtime.lock`。`--system-site-packages` 用于复用系统安装的 `python3-clang-18`，避免自行编译或下载不匹配的 Clang binding。

   备选方案是全局 `pip install`，但会污染系统 Python；`uv` 或 `pipenv` 当前收益不明显，会增加镜像工具链复杂度。

2. **运行时显式请求并校验 schema v2**

   KB 扫描命令必须传入 `--schema-version 2.0`。后端读取结果时校验 `schemaVersion == "2.0"`，否则任务失败并记录明确错误。这样避免 scanner 默认值变化或旧脚本输出混入后端。

3. **用 v2 DTO 替换 v1 DTO**

   后端 DTO 应围绕 `scan`、`summary`、`findings[].fact`、`findings[].conclusion`、`findings[].occurrences`、`findings[].evidenceChain` 建模。旧的 `rule_id/file/line/reason/suggestion` 扁平字段不再作为输入合同。

4. **数据库 `findings` 表作为查询投影，完整 v2 finding 存入 evidence**

   现有 `findings` 表适合承担分页、排序、过滤、报告纳入状态、迁移输入引用等查询场景，因此不需要把所有能力改成大 JSON 查询。导入时从 v2 finding 投影出稳定字段：

   - `rule_id`: 使用 v2 finding id 或主要规则标识。
   - `severity`: 使用 `conclusion.severity`。
   - `title`: 使用 `conclusion.title`。
   - `file_path/start_line/end_line`: 使用 `fact.primaryLocation`。
   - `finding_type/source_kind`: 使用 `conclusion.findingType` 和 `fact.kind`。
   - `evidence`: 保存完整 v2 finding payload。

5. **API 返回 v2 优先结构**

   列表 API 返回用于表格展示和过滤的摘要字段，并增加 v2 的 `fact`、`conclusion` 摘要。详情 API 返回完整 v2 finding，包括 `occurrences` 和 `evidenceChain`。代码上下文接口继续由后端读取源码目录生成前后文，并与 v2 primary location 对齐。

6. **AI 扩展输入读取 v2 finding**

   AI 扩展导出的输入文件应包含完整 v2 finding、可用源码上下文、已有人工状态和必要项目上下文。Agent 可以在信息不足时读取项目源码，但不能依赖旧 v1 trace 字段。

## Risks / Trade-offs

- **镜像体积增加** -> Clang/libclang 和 Python runtime 会增加后端镜像体积；通过 lock 文件和 venv 固定依赖，换取运行一致性。
- **历史 v1 数据字段不完整** -> 历史 finding 可能缺少 v2 evidence；新接口对历史数据可返回空 v2 payload 或兼容性提示，但新任务必须产出 v2。
- **scanner 依赖包在基础镜像源中不可用** -> 构建阶段需要显式失败，不能静默降级到 v1。
- **v2 finding 缺少 primary location** -> 导入仍应保存 finding，并将位置字段置空，详情中保留原始 evidence 供审计。
- **前端短期不兼容** -> 本 change 是后端破坏性合同更新，前端会后续配套升级。

## Migration Plan

1. 更新后端 Dockerfile，安装 `python3-venv`、`clang-18`、`libclang-18-dev`、`python3-clang-18`，创建 KB Scanner venv 并安装 runtime lock。
2. 更新后端配置，默认使用 venv Python 执行 scanner。
3. 更新 KB 扫描运行命令，传入 `--schema-version 2.0`。
4. 替换 scanner 结果 DTO 和 mapper，导入 v2 finding 并保存完整 evidence。
5. 更新 KB finding 列表、详情、上下文、artifact 下载、AI 扩展输入和报告输入预览的后端消费逻辑。
6. 补齐单元测试和 E2E，使用真实 schema v2 `scan-result.json` 验证运行链路。
7. 重建后端容器并运行 KB 扫描 E2E。

回滚方式：回滚到上一版后端镜像和代码。scanner CLI 仍可输出 v1，但本 change 不提供运行时自动回退。

## Open Questions

- 历史 v1 artifact 是否需要离线迁移为 v2 结构？当前按不迁移处理。
