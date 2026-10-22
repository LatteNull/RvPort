## Why

当前后端已经为源码版本和运行环境配置保存了版本字段，但部分节点列表接口默认仍返回项目下历史记录，导致前端在更新源码或运行环境后仍可能看到旧构建、旧依赖分析或旧 KB 扫描结果。评估报告也缺少“最新报告是否已经覆盖当前确认输入”的明确状态，节点结果列表缺少“该条是否已纳入报告”的统一表达。

## What Changes

- 统一当前节点视图的版本收敛规则：默认按 active source revision 和当前 runtime environment version 过滤当前节点数据。
- 保留历史记录，不做物理删除；历史查看必须通过显式参数查询。
- 构建验证、依赖分析、KB 扫描等节点列表返回记录陈旧状态，避免前端误把历史结果当作当前结果。
- 评估报告 readiness/detail 增加报告更新状态，用当前 confirmed migration input refs 与最新报告输入快照比较。
- KB finding、依赖分析结果等可进入报告的节点结果列表增加报告纳入状态，告诉前端该条是否已进入最新报告、是否会进入下一次报告。
- 补充单元测试和 E2E 覆盖正常流程、异常流程和 edge case。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `build-validation-runtime`: 构建验证列表需要默认返回当前源码版本和当前运行环境配置下的记录，并支持显式查看历史记录。
- `dependency-analysis-runtime`: 依赖分析运行和结果需要默认绑定当前源码版本/当前运行环境配置，并返回报告纳入状态。
- `kb-scan-runtime`: KB 扫描运行和 finding 列表需要默认绑定当前源码版本，并返回报告纳入状态。
- `migration-report-runtime`: 报告 readiness/detail 需要返回报告是否落后于当前确认输入，以及变化摘要。
- `node-local-migration-input-confirmation`: 节点内确认状态需要能被节点结果列表直接表达为报告纳入状态。
- `project-runtime-environment-selection`: 运行环境更新后，依赖环境的节点结果必须被视为非当前结果。

## Impact

- 影响后端 API：构建列表、依赖分析列表与结果列表、KB 扫描列表与 finding 列表、评估报告 readiness/detail、报告输入预览。
- 影响服务层：需要统一解析 active source revision、current runtime environment version，并计算 stale/current 状态。
- 影响查询层：需要增加可选过滤参数、报告输入快照对比查询、migration input ref / report input 关联查询。
- 影响测试：需要覆盖源码变更、运行环境变更、报告生成后输入变化、节点结果纳入/撤回报告等场景。
