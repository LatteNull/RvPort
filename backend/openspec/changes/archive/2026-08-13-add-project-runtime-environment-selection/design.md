## Context

当前远程环境选择分散在多个接口：SBOM 创建请求传 `sourceEnvironmentId` 和 `targetEnvironmentId`，源码部署请求传 `environmentIds`，构建验证通过 `sourceDeploymentIds` 间接选择环境，自动化测试请求仍传 `environmentId`。这种分散选择会导致同一项目的 SBOM 结果、构建结果和测试结果来自不同远程环境，最终报告缺少一致性基础。

产品决策是将环境选择前置到环境管理中，项目维护一组当前运行环境：源环境和目标环境。所有依赖远程环境运行的节点都从这组配置读取环境。双环境是运行前置条件；设置接口可以一次只改一个环境，但运行节点必须在双环境完整时才允许继续。

## Goals / Non-Goals

**Goals:**
- 提供项目级当前运行环境配置，包含源环境和目标环境。
- 支持一次设置一个环境，也支持同时设置两个环境。
- 远程运行节点必须要求双环境完整。
- SBOM、源码部署、构建验证和自动化测试统一使用项目当前运行环境。
- 通过环境配置版本判断历史结果是否属于当前运行环境。
- 源码更新只影响源码相关运行结果，不影响环境检查和环境快照本身。

**Non-Goals:**
- 不支持单环境迁移评估流程。
- 不在本 change 设计多套环境组、用户级环境组或项目成员权限。
- 不删除历史 SBOM、部署、构建、测试记录。
- 不要求源码上传或 Git 同步触发环境重新检测。

## Decisions

### 新增项目运行环境配置表

新增 `project_runtime_environments` 表，建议字段：
- `project_id`
- `source_environment_id`
- `target_environment_id`
- `version`
- `updated_by`
- `created_at`
- `updated_at`

该表一项目一行，`source_environment_id` 和 `target_environment_id` 都允许为空，支持设置接口局部更新。但运行节点读取时必须要求两者都不为空。

### 使用版本号表达环境配置有效性

每次 source 或 target 环境变更，`version` 递增。环境相关运行记录保存创建时的 `environment_config_version`。

影响表：
- `sbom_runs`
- `source_deploy_runs`
- `build_runs`
- `test_runs`

查询详情和列表时返回 `environmentConfigVersion` 与 `currentEnvironmentConfigVersion`，由后端计算 `isCurrentRuntimeEnvironment`。旧结果不删除、不改终态，只标识为非当前环境结果。

### 运行节点不再接受环境选择字段

新语义：
- SBOM 创建：请求体不再传 `sourceEnvironmentId`、`targetEnvironmentId`，后端从项目运行环境读取。
- 源码部署：请求体不再传 `environmentIds`，后端部署到项目运行环境中的 source 和 target。
- 构建验证：请求体不再传 `sourceDeploymentIds`，后端基于当前源码版本、当前运行环境版本和成功部署记录创建构建；缺少部署时返回明确错误。
- 自动化测试：请求体不再传 `environmentId`，测试环境来自关联构建运行；如果后续支持双环境测试，应由构建运行集合或后端当前构建结果决定。

### 环境配置变更不自动重跑

环境配置变更只递增版本，并使历史环境相关结果不再属于当前环境配置。是否重跑由前端引导用户触发，不由设置接口自动触发任务。

## Risks / Trade-offs

- 旧前端仍提交环境字段 → 后端可短期忽略或返回明确废弃错误；建议返回参数错误，防止用户误以为字段生效。
- 已有运行记录缺少版本字段 → migration 可以为历史记录填充 `1` 或 `0`，并在当前环境配置存在后由查询层标识为非当前或未知。
- 构建验证依赖部署记录，用户未先部署 → 返回 `SOURCE_DEPLOYMENT_NOT_READY` 或新增明确错误，引导先执行源码部署。
- 双环境设置允许局部更新，但运行要求双环境 → 设置接口成功不代表项目可运行；查询接口必须返回 `ready=false` 和缺失字段。

## Migration Plan

1. 新增 `project_runtime_environments` 表和运行记录版本字段。
2. 为已有项目按可用环境尝试初始化运行环境配置；无法确定时保持空配置。
3. 修改环境管理 API 增加查询和局部更新项目运行环境。
4. 修改 SBOM、源码部署、构建验证和自动化测试创建逻辑，从项目运行环境读取环境。
5. 更新列表/详情/overview 返回当前环境版本有效性。
6. 更新 E2E，覆盖缺少双环境失败、局部设置、完整双环境运行和环境变更后结果过期。
