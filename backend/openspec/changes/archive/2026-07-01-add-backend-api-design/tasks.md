## 1. API 设计文档

- [x] 1.1 基于根目录 `docs/design/01_API_DESIGN.md` 创建 `backend/docs/API_DESIGN.md`。
- [x] 1.2 将文档语言统一为中文，保留接口路径、字段名和枚举值英文。
- [x] 1.3 记录 API base path、认证方式、响应包络、错误响应、分页格式和时间格式。
- [x] 1.4 明确 API 文档与数据库设计之间的映射关系。

## 2. 核心 API 边界

- [x] 2.1 设计认证 API，确保 `GET /auth/me` 不返回角色或权限模型，只返回本地用户和 `isSuperAdmin`。
- [x] 2.2 设计当前用户修改密码 API，并在 `GET /auth/me` 中暴露 `mustChangePassword`。
- [x] 2.3 设计超级管理员用户管理 API，覆盖配置页用户列表、创建用户、读取用户、更新用户、禁用/删除用户和重置密码。
- [x] 2.4 明确 `isSuperAdmin` 不允许通过 API 创建或修改，只能通过初始化脚本或数据库维护方式设置。
- [x] 2.5 标注 API 设计依赖数据库补充字段：`users.must_change_password boolean not null default false`。
- [x] 2.5.1 补充数据库设计文档和 OpenSpec delta spec，正式加入 `users.must_change_password` 字段。
- [x] 2.6 设计项目 API，说明 `stage` 是导航提示，真实状态由 overview 聚合。
- [x] 2.7 设计源码版本 API，覆盖压缩包上传、Git 同步、当前版本切换和修复后代码重新入库。
- [x] 2.8 设计环境与凭据 API，明确凭据写入、遮蔽展示和禁止明文返回。

## 3. 异步任务、SSE 与日志

- [x] 3.1 统一任务状态枚举，补齐 `QUEUED`。
- [x] 3.2 明确所有长任务创建接口只返回 `taskId` 和初始状态。
- [x] 3.3 统一项目级 SSE：`GET /api/projects/{projectId}/task-events`。
- [x] 3.4 明确 `GET /tasks/{taskId}` 和 `GET /tasks/{taskId}/logs` 是 SSE 断线补偿。
- [x] 3.5 明确完整日志本地保存，API 只返回分页内容、摘要或受控下载，不暴露服务器真实路径。

## 4. 领域 API

- [x] 4.1 设计 KB 扫描 API，覆盖扫描任务、扫描摘要、findings 列表和加入问题清单。
- [x] 4.2 设计 SBOM API，覆盖分析任务、组件列表、候选替代项和加入问题清单。
- [x] 4.3 设计迁移问题 API，覆盖确认、忽略、解决、批量更新和来源追溯。
- [x] 4.4 设计报告与复检 API，覆盖评估报告、报告输入、修复后复检和 diff。
- [x] 4.5 设计构建与测试 API，测试 API 限定为退出码和汇总计数，不承诺用例级能力。
- [x] 4.6 设计归档与审计 API，归档下载使用业务资源接口，不引入通用 Artifact API。

## 5. 校验

- [x] 5.1 对照 `backend/docs/DATABASE_DESIGN.md` 检查 API 是否仍引用通用 artifacts、roles、user_roles、project_members 或测试用例解析。
- [x] 5.2 对照根目录 API 设计确认保留了必要页面触发和字段映射。
- [x] 5.3 使用 `openspec validate add-backend-api-design` 校验 change。
