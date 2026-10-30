## Why

源码激活时即创建优化轮次，但项目 overview 当前只凭轮次存在将 `OPTIMIZE` 标记为 `DONE`，导致构建和测试尚未执行时优化闭环已显示完成。优化摘要仅按源码聚合历史记录，latest 在缺少 active 源码时还可能把历史轮次标成 `CURRENT`，需要统一当前验证链的有效性规则。

## What Changes

- 保留按源码创建、复用轮次的行为，明确轮次生命周期与验证完成是两个概念；只有当前有效的双端构建、双端测试及通过的测试比较链全部满足，优化闭环才能完成。
- 引入后端共享的验证事实解析，统一项目 overview、优化 overview、latest 和当前轮次摘要；按当前源码、环境及配置版本、构建引用、测试批次和比较输入判断有效性。
- 明确源码切换、环境变更、重新构建或测试、失败重试和旧数据缺少关联字段时的失效规则，保留历史记录供审计，不回退旧成功结果填补当前缺口。
- 保留现有 latest 外壳、API 路径、轮次生命周期枚举及前端消费的摘要字段；通过后端兼容字段修复现有流程图与当前轮次下一步提示，不修改前端代码或前端 OpenSpec。
- 保持 optimize readiness 的查看语义；读取轮次不要求验证链已经完成，也不自动触发任务或作出优化收敛决策。
- 增加 Docker 单元测试、整体及受影响模块行/分支覆盖率至少 90% 自动门槛，以及独立资源下的完整根 Compose 构建、启动和业务验收任务。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `optimization-cycle-runtime`：规定验证完成条件、有效证据选择、历史失效与 latest 新鲜度，保留按源码组织轮次和只读聚合边界。
- `backend-api-design`：规定 overview、latest 和兼容摘要的一致性、前端对接契约、readiness 查看语义和快照一致性。

## Impact

- 后端预计涉及 `optimization`、`project`、`workflow`，以及构建、测试、比较记录查询与对应单元测试；仅在共享解析确有需要时调整 `buildvalidation`、`automatedtest`、`testcomparison` 内部查询。
- 保留现有数据库历史事实；优先利用已有源码、环境配置版本、`buildRunId`、`testBatchId` 和比较两侧测试 ID，无计划增加持久化的“轮次通过”状态。
- API 调整以现有字段语义修正和可选增量字段为限；前端当前按 workflow 状态及 `summary.build/test.latestStatus`、`summary.testComparison` 判断下一步，必须以这些现有消费点验收后端兼容性。
- 不修改前端、工具业务逻辑，不新增 CI/E2E 或真实 SSH 验证设施，不改变归档 API 现有授权与业务规则。完整 Docker 验收仍包含默认前端服务的构建和健康检查。
