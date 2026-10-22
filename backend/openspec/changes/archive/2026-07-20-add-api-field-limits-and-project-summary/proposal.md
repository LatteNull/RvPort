## Why

飞书联调文档指出当前认证输入边界和项目列表展示信息仍有缺口：登录、改密和设密类接口缺少统一最大长度约束，项目列表缺少卡片摘要字段。与此同时，项目名称重名策略需要明确，避免后端在未来多用户共享项目设计前过早加入唯一约束。

## What Changes

- 为认证相关接口统一增加字段长度约束：`username` 最大 64 字符，所有明文 `password` 输入最大 16 字符。
- 在数据库层为 `users.username` 增加最大 64 字符检查约束；密码不保存明文，只在 API 层校验最大长度。
- 保持普通 text 字段现有设计，不扩大本 change 到 display name、description、email、配置项等其他 text 字段。
- 为 `GET /api/projects` 的列表项增加轻量项目摘要字段，用于前端项目卡片展示高风险数、最近扫描时间、最近构建状态和最近测试状态。
- 明确项目名称允许重名，不增加 `projects.name` 唯一约束；后续多用户共享项目和项目可识别信息另行设计。
- 更新中文 API、数据库、项目能力文档，并补充单元测试和 E2E 覆盖。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `backend-api-design`: 增加认证字段最大长度要求，更新项目列表响应摘要字段，明确项目名称允许重名。
- `backend-database-design`: 增加 `users.username` 最大长度数据库约束，并明确 `projects.name` 不做唯一约束。
- `project-source-environment`: 修改项目列表 requirement，要求列表项包含项目卡片摘要字段，并明确创建项目允许同名。

## Impact

- API 请求对象：登录、当前用户改密、邀请接受、忘记密码确认、管理员重置密码，以及管理员创建用户中的 `username`。
- 数据库迁移：新增 Liquibase changeset，为 `users.username` 增加长度 check constraint；不修改密码哈希存储，不增加项目名称唯一索引。
- 项目列表查询：需要聚合或补齐 `highRiskCount`、`latestScanAt`、`latestBuildStatus`、`latestTestStatus` 字段。
- 文档和测试：更新 `backend/docs/API_DESIGN.md`、数据库/项目相关文档、OpenSpec specs、单元测试和模块化 E2E。
