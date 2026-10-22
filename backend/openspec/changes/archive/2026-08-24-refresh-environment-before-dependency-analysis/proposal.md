## Why

依赖分析当前直接使用数据库中最近一次成功环境快照，环境被安装、删除软件或切换软件源后，如果没有手动重新采集，会产生过期判断。例如目标 RISC-V 环境中 `gcc` 已删除，但依赖分析仍可能根据旧快照返回 `TARGET_INSTALLED`。

## What Changes

- 依赖分析任务执行前默认刷新 source/x86 和 target/RISC-V 环境采集结果。
- 依赖分析必须使用本次刷新产生的成功快照作为匹配依据。
- 任一环境采集失败时，依赖分析任务失败并返回可审计错误，不再降级使用旧快照。
- 依赖分析制品和详情需要记录本次使用的 source/target snapshot id 与采集时间。
- E2E 增加 stale snapshot 场景覆盖，验证目标环境变化后分析结果来自刷新后的快照。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `dependency-analysis-runtime`: 依赖分析执行前刷新 source/target 环境快照，并强制使用新快照。
- `api-e2e-test-suite`: 增加依赖分析刷新环境快照的端到端覆盖。

## Impact

- 影响依赖分析任务执行流程、任务日志和错误处理。
- 影响 `DependencyAnalysisHandler` 对环境快照的获取方式。
- 可能复用或抽取环境采集 runtime 能力，避免通过旧 snapshot 进行匹配。
- 依赖分析耗时会增加，失败面会包含 SSH 环境采集失败。
- API 请求参数暂不暴露跳过刷新开关，默认保证分析正确性。
