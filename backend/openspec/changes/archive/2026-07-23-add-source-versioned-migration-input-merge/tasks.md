## 1. 数据库与 jOOQ

- [x] 1.1 新增 Liquibase changeset 创建 `migration_input_sets` 和 `migration_input_refs`
- [x] 1.2 为 `migration_input_sets` 添加源码版本唯一 active 集合约束和查询索引
- [x] 1.3 为 `migration_input_refs` 添加状态检查约束、重复导入唯一约束和列表查询索引
- [x] 1.4 运行 Liquibase 迁移验证空库和既有库可升级
- [x] 1.5 运行 jOOQ codegen 并提交生成代码

## 2. 领域模型与 Repository

- [x] 2.1 新增迁移输入集合和 reference 的 Java DTO、枚举和值对象
- [x] 2.2 实现 `MigrationInputRepository` 的集合获取或创建、列表分页、详情读取、批量插入和状态更新
- [x] 2.3 实现重复导入幂等处理并返回 created/skipped 计数
- [x] 2.4 实现迁移输入列表过滤和排序白名单
- [x] 2.5 确保所有 repository 查询不返回服务器真实路径或敏感字段

## 3. 来源解析与导入服务

- [x] 3.1 实现 `MigrationInputSourceResolver` 按 `sourceType` 解析真实来源记录
- [x] 3.2 实现 KB finding 导入校验：项目归属、源码版本归属、severity、location label 和建议摘要
- [x] 3.3 实现 SBOM result item 导入校验：项目归属、`detectedLevel=riskLevel/targetMatchStatus`、location label 和建议摘要
- [x] 3.4 实现批量导入 service，支持单条和多条 `sourceRefIds`
- [x] 3.5 实现迁移输入详情 service，按来源返回 typed detail

## 4. 自动合并

- [x] 4.1 设计并实现自动合并请求来源枚举
- [x] 4.2 实现代码类来源自动合并：按当前 `sourceRevisionId` 查找当前有效结果
- [x] 4.3 实现 SBOM 来源自动合并：按当前项目查找最新成功 SBOM 分析结果
- [x] 4.4 自动合并复用批量导入逻辑并返回按来源分组的 created/skipped/noResult 计数
- [x] 4.5 明确当前不做冲突检测，仅重复项幂等跳过

## 5. API

- [x] 5.1 新增迁移输入列表接口 `GET /api/projects/{projectId}/source-revisions/{sourceRevisionId}/migration-inputs`
- [x] 5.2 新增批量导入接口 `POST /api/projects/{projectId}/source-revisions/{sourceRevisionId}/migration-inputs:import`
- [x] 5.3 新增自动合并接口 `POST /api/projects/{projectId}/source-revisions/{sourceRevisionId}/migration-inputs:auto-merge`
- [x] 5.4 新增详情接口 `GET /api/migration-inputs/{migrationInputId}`
- [x] 5.5 新增状态更新接口 `PATCH /api/migration-inputs/{migrationInputId}`
- [x] 5.6 所有接口执行项目访问校验、源码版本归属校验和统一错误响应

## 6. 源码版本与报告接入

- [x] 6.1 在源码版本成功创建后确保迁移输入集合可用，且不复制旧版本 reference
- [x] 6.2 确保失败源码入库不创建可用迁移输入集合
- [x] 6.3 调整报告生成输入来源，只读取当前源码版本下 `CONFIRMED` migration input refs
- [x] 6.4 报告生成按 `sourceType + sourceRefId` 回查真实详情并过滤 `CANDIDATE`、`EXCLUDED`
- [x] 6.5 无 confirmed 输入时返回明确业务错误或受控空报告摘要

## 7. 测试

- [x] 7.1 补充数据库迁移测试或验证脚本，确认表、约束和索引存在
- [x] 7.2 补充 repository/service 正常流程测试：集合创建、分页列表、批量导入、详情、状态更新
- [x] 7.3 补充异常流程测试：跨项目、跨源码版本、来源记录不存在、非法状态、非法排序字段
- [x] 7.4 补充 edge case 测试：空列表、重复导入、单条导入、SBOM 缺少版本或路径 fallback、KB 无行号 fallback
- [x] 7.5 补充报告输入过滤测试，确认只有 `CONFIRMED` reference 被消费
- [x] 7.6 更新 API E2E 模块，覆盖 KB finding 导入、SBOM result 导入、自动合并、状态确认和源码版本隔离

## 8. 文档与验证

- [x] 8.1 更新 `backend/docs/API_DESIGN.md`，补充迁移输入合并 API 和报告输入规则
- [x] 8.2 更新 `backend/docs/api-e2e-coverage.md`，补充迁移输入 E2E 覆盖点
- [x] 8.3 运行相关 Maven 单元测试
- [x] 8.4 运行相关 E2E module
- [x] 8.5 运行完整 Maven 测试
- [x] 8.6 运行 `openspec validate add-source-versioned-migration-input-merge`
