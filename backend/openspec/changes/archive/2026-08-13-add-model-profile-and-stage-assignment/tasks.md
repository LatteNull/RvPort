## 1. 数据库和代码生成

- [x] 1.1 新增 Liquibase changelog 创建 `model_profiles` 表，包含名称、启用状态、provider 类型、base URL、模型名、wire API、API key 加密载荷、超时、最近测试摘要和审计时间字段。
- [x] 1.2 新增 Liquibase changelog 创建 `model_stage_assignments` 表，包含阶段枚举、模型 profile 外键、唯一约束和审计时间字段。
- [x] 1.3 为 `model_profiles.name`、`model_profiles.enabled`、`model_profiles.last_tested_at` 和 `model_stage_assignments.stage` 增加必要唯一约束和索引。
- [x] 1.4 设计并实现从历史 `system_configs.codex-provider` 配置迁移到默认模型 profile 的兼容策略。
- [x] 1.5 运行 Liquibase 迁移并使用 jOOQ 脚本刷新生成源码。

## 2. 模型 Profile 领域实现

- [x] 2.1 新增模型 profile DTO、枚举、请求解析器、响应对象和分页查询对象。
- [x] 2.2 新增模型 profile repository，支持创建、查询、分页列表、更新、删除检查和测试摘要更新。
- [x] 2.3 新增模型 profile service，校验名称唯一、provider 类型、base URL、模型名、wire API、超时范围和 API key 保存语义。
- [x] 2.4 复用现有加密能力保存 API key，并保证响应、日志和异常摘要只返回遮蔽状态。
- [x] 2.5 将现有 Codex provider 探测能力改造为接收模型 profile resolved config。

## 3. 阶段绑定和运行时解析

- [x] 3.1 新增阶段枚举，本 change 只包含 `TEST_LOG_COMPARE`。
- [x] 3.2 新增阶段绑定 repository 和 service，支持查询所有阶段绑定、批量保存绑定和按阶段解析 profile。
- [x] 3.3 保存绑定时校验阶段白名单、profile 存在且启用，并保证非法输入不产生部分写入。
- [x] 3.4 运行时按阶段解析模型时，对未绑定或绑定禁用 profile 返回明确业务错误。
- [x] 3.5 保证业务任务请求不能绕过阶段绑定直接提交 base URL、API key 或任意模型参数。

## 4. 管理员 API

- [x] 4.1 新增 `GET /api/admin/model-profiles` 分页列表接口，支持过滤和排序白名单。
- [x] 4.2 新增 `POST /api/admin/model-profiles`、`GET /api/admin/model-profiles/{profileId}`、`PATCH /api/admin/model-profiles/{profileId}` 和删除接口。
- [x] 4.3 新增 `POST /api/admin/model-profiles/{profileId}:test`，支持已保存配置和临时覆盖配置测试。
- [x] 4.4 新增 `GET /api/admin/model-stage-assignments` 和 `PATCH /api/admin/model-stage-assignments`。
- [x] 4.5 保证所有模型配置 API 仅超级管理员可访问，普通用户返回无权限错误且不泄漏内部信息。
- [x] 4.6 移除旧 `/api/admin/configs/codex-provider` 管理入口，保留历史 `system_configs.codex-provider` 到默认模型 profile 的一次性迁移。

## 5. 测试和验证

- [x] 5.1 补充 Liquibase migration 测试，验证新表、约束、索引和历史配置迁移。
- [x] 5.2 补充模型 profile service 单元测试，覆盖正常流程、异常流程和 edge case。
- [x] 5.3 补充阶段绑定 service 单元测试，覆盖合法绑定、未知阶段、禁用 profile、未绑定解析和事务回滚。
- [x] 5.4 补充 Codex provider 探测测试，验证 profile 参数传入和错误脱敏。
- [x] 5.5 补充管理员 API 安全测试，验证普通用户不能访问模型配置接口。
- [x] 5.6 补充独立 API E2E 模块，覆盖创建 profile、查询列表、测试配置、保存阶段绑定和非法输入。
- [x] 5.7 运行 `mvn test`。
- [x] 5.8 在基础设施和后端可用时运行对应 E2E 模块并清理测试数据。
- [x] 5.9 运行 `openspec validate add-model-profile-and-stage-assignment --strict`。
