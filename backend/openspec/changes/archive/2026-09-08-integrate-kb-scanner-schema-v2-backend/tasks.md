## 1. 运行环境

- [x] 1.1 更新后端 Dockerfile，安装 `python3-venv`、`clang-18`、`libclang-18-dev`、`python3-clang-18` 和新版 KB Scanner 所需基础工具
- [x] 1.2 在镜像中为 `tools/kb-scanner` 创建隔离 Python venv，并安装 `requirements/runtime.lock`
- [x] 1.3 更新 compose/env 配置，使 API 和 worker 都使用 venv Python 执行 KB Scanner
- [x] 1.4 在容器内验证 venv 可以导入 `kb_scanner`、`tree_sitter` 和 `clang.cindex`

## 2. Scanner 运行时与 DTO

- [x] 2.1 将 KB 扫描命令改为显式传入 `--schema-version 2.0`
- [x] 2.2 替换旧 v1 `KbScannerResult` DTO，新增或改造为 schema v2 结构
- [x] 2.3 将扫描结果版本校验改为只接受 `schemaVersion: "2.0"`
- [x] 2.4 更新 scanner 失败、缺失结果文件、版本不兼容和 JSON 解析异常的错误信息

## 3. Finding 入库与领域映射

- [x] 3.1 将 v2 `fact.primaryLocation`、`conclusion`、`occurrences` 和 `evidenceChain` 映射到现有 finding 查询投影
- [x] 3.2 将完整 v2 finding payload 保存到 evidence 字段
- [x] 3.3 支持缺少 primary location 的 finding 导入，并保证详情仍可审计
- [x] 3.4 更新 structured diagnostics、summary 和 artifact metadata 的保存逻辑
- [x] 3.5 确认报告纳入状态、人工确认状态和迁移输入引用仍基于当前 finding 记录工作

## 4. API 改造

- [x] 4.1 更新 KB finding 列表 API，返回 v2 优先的摘要字段、分页、排序、过滤和报告纳入状态
- [x] 4.2 更新 KB finding 详情 API，返回完整 v2 finding、人工状态、报告纳入状态和 AI 扩展建议
- [x] 4.3 更新代码上下文 API，使其基于 v2 primary location 或投影位置读取源码上下文
- [x] 4.4 更新 artifact 下载 API，确保 JSON 和 HTML 都绑定 schema v2 扫描结果
- [x] 4.5 移除或停止默认使用旧 v1 API DTO 合同

## 5. AI 扩展与报告消费

- [x] 5.1 更新 KB AI 扩展输入导出，使用 v2 finding、源码上下文和当前人工状态
- [x] 5.2 更新 AI 扩展结果写入逻辑，允许部分结果写入且不影响未生成建议的 finding
- [x] 5.3 更新报告输入预览和报告生成读取逻辑，使其消费 v2 evidence 和投影字段

## 6. 测试与验证

- [x] 6.1 增加 schema v2 DTO 解析和 mapper 单元测试，覆盖正常流程、异常流程和 edge case
- [x] 6.2 增加 KB finding API 单元或集成测试，覆盖列表、详情、代码上下文和 artifact 下载
- [x] 6.3 更新 API E2E 模块，使用真实 KB Scanner v2 输出验证扫描、查询、详情和下载链路
- [x] 6.4 增加非 v2 结果拒绝、缺少 primary location、空 findings 和结构化 diagnostics 的 E2E 或 fixture 覆盖
- [x] 6.5 重建后端容器并运行相关 Maven 测试
- [x] 6.6 启动 Docker 环境后运行 KB 扫描真实 E2E，确认 artifact、finding 和 API 返回均为 schema v2
