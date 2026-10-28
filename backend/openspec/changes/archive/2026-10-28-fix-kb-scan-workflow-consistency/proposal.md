## Why

知识库扫描的 readiness 要求当前 x86 构建成功，但创建接口未强制校验，worker 在没有构建时仍可完成纯源码扫描；overview 和 latest 又只按源码版本认定当前结果，导致重新配置环境或尚未构建时仍显示“已完成”。需要统一执行准入和结果有效性，避免过期扫描被当作当前工作流事实。

## What Changes

- **BREAKING**：创建 KB 扫描必须满足所扫描源码、当前运行环境版本下的 x86 `SOURCE_ONLY` 构建成功条件；未满足时返回现有 `409 PREREQUISITE_NOT_SATISFIED`，不创建任务、运行记录或队列消息。
- 持久化扫描采用的源码、源环境、运行环境配置版本和构建 ID；worker 使用固定构建，禁止执行时自动切换到其他成功构建。
- 统一 overview、KB latest、当前结果查询与报告的 KB 前置事实判定。当前有效扫描成功才能贡献 `DONE`；历史成功记录保持原终态，按失效规则返回 `STALE`，不再作为当前结果。
- 明确新构建进行中、失败、取消、超时，以及源码或运行环境版本变化时的失效行为；旧记录缺少完整上下文时保守视为历史，不猜测回填。
- 将“未完成成功构建”与“成功构建缺少编译数据库”分开：前者阻止扫描，后者仍允许 `NOT_AVAILABLE` 或 `FALLBACK` 降级，并记录绑定构建与原因。
- 补齐正常、边界、异常和并发场景的单元测试，复用 Docker 验证入口和 JaCoCo 整体及受影响包行/分支覆盖率至少 90% 的自动门槛。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `kb-scan-runtime`：统一创建与执行前置条件、固定构建上下文、latest 有效性、历史失效及降级边界。
- `backend-api-design`：明确 KB 在 overview、readiness、latest 和执行接口之间的一致性契约及安全错误语义。
- `backend-database-design`：保存扫描执行上下文和构建关联，支持当前/历史记录筛选与旧数据兼容。

## Impact

- 范围限定 `D:\projects\RvPort\backend`：KB service/repository/runtime、工作流聚合、readiness、KB 结果消费者、Liquibase/jOOQ、相关 DTO、接口文档和单元测试。
- 保留 API 路径、任务状态枚举和 latest 外壳；增加安全上下文/有效性原因字段时提供中英文展示文案。显式指定本项目历史源码的扫描仍可支持，但必须校验该源码自己的构建，结果不得占用当前 active source 的状态。
- 不修改独立 KB Scanner 的扫描算法，不新增 CI、E2E 或真实 SSH 测试设施，不改变其他分析节点的有效性规则，不删除历史扫描、finding 或 artifact。
- 当前仅交付 OpenSpec 提案；实施阶段从仓库根目录以独立 Docker 容器验证，并在所有验收通过后才具备归档条件。历史覆盖率缺口若超出本变更范围，应报告差距并请求扩大范围。
