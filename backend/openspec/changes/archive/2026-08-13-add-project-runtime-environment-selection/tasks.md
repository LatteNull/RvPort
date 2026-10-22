## 1. 数据库和模型

- [x] 1.1 新增 Liquibase changelog 创建 `project_runtime_environments` 表，支持项目一行、source/target 环境可空、版本号和审计字段。
- [x] 1.2 为 `sbom_runs`、`source_deploy_runs`、`build_runs` 和 `test_runs` 增加 `environment_config_version` 字段和必要索引。
- [x] 1.3 设计历史数据兼容策略，确保旧运行记录不会被删除，并能被标识为未知或非当前环境版本。
- [x] 1.4 运行 Liquibase 迁移并使用 jOOQ 脚本刷新生成源码。

## 2. 项目运行环境配置 API

- [x] 2.1 新增运行环境配置 DTO、repository、service 和响应对象。
- [x] 2.2 实现 `GET /api/projects/{projectId}/runtime-environments`，返回 source/target 摘要、版本、ready 状态和缺失项。
- [x] 2.3 实现 `PATCH /api/projects/{projectId}/runtime-environments`，支持只设置 source、只设置 target 或同时设置两者。
- [x] 2.4 校验运行环境属于同一项目、已启用、角色匹配且不能引用非法环境。
- [x] 2.5 环境配置每次实际变更只递增一次版本，并记录更新人和更新时间。
- [x] 2.6 更新项目 overview，返回当前运行环境配置摘要和 ready 状态。

## 3. 运行节点环境来源收敛

- [x] 3.1 修改 SBOM 创建请求，不再要求 `sourceEnvironmentId` 和 `targetEnvironmentId`，改为读取项目运行环境配置。
- [x] 3.2 修改源码部署创建请求，不再要求 `environmentIds`，改为部署到项目运行环境配置中的 source 和 target。
- [x] 3.3 修改构建验证创建请求，不再要求 `sourceDeploymentIds`，改为基于当前环境配置和成功源码部署记录创建双环境构建。
- [x] 3.4 修改自动化测试创建请求，不再要求 `environmentId`，改为从关联构建运行确定测试环境。
- [x] 3.5 所有运行节点创建前校验双环境完整，缺失时返回明确业务错误且不创建任务、运行记录或队列消息。
- [x] 3.6 运行记录和任务输入快照保存环境 ID 和 `environmentConfigVersion`。

## 4. 有效性和兼容

- [x] 4.1 在 SBOM、源码部署、构建和测试列表/详情响应中返回 `environmentConfigVersion`、当前版本和 `isCurrentRuntimeEnvironment`。
- [x] 4.2 环境配置变更后，旧运行记录保留历史状态但在查询中标识为非当前环境结果。
- [x] 4.3 源码版本更新不改变运行环境配置版本，但源码相关结果按源码版本继续区分有效性。
- [x] 4.4 对旧请求字段制定兼容策略，明确忽略或返回参数错误，防止前端误以为仍可单独选择环境。
- [x] 4.5 禁用当前运行环境引用的环境时，拒绝禁用或要求先解除运行环境配置。

## 5. 测试和验证

- [x] 5.1 补充 migration 测试，验证新表、版本字段、约束和索引。
- [x] 5.2 补充运行环境配置 service 测试，覆盖局部设置、同时设置、非法环境、跨项目、禁用环境和版本递增。
- [x] 5.3 补充 SBOM、源码部署、构建验证和自动化测试 service 测试，覆盖双环境缺失、双环境完整和环境版本写入。
- [x] 5.4 补充查询响应测试，验证旧版本运行记录返回 `isCurrentRuntimeEnvironment=false`。
- [x] 5.5 更新独立 API E2E，覆盖设置 source、设置 target、完整双环境后创建运行任务，以及环境变更后旧结果过期。
- [x] 5.6 运行 `mvn test`。
- [x] 5.7 在基础设施和后端可用时运行相关 E2E 模块并清理测试数据。
- [x] 5.8 运行 `openspec validate add-project-runtime-environment-selection --strict`。
