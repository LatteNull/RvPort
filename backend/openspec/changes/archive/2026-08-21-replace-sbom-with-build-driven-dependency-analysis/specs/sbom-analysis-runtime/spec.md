## ADDED Requirements

### Requirement: SBOM 分析主流程必须标记为 deprecated
SBOM 分析运行时 SHALL 保留旧 API、旧任务类型和历史数据兼容，但 SHALL 在新迁移主流程中标记为 deprecated。

#### Scenario: 保留历史 SBOM 查询
- **WHEN** 用户查询历史 SBOM 分析记录、结果明细或 artifact
- **THEN** 后端 SHALL 在权限校验通过后继续返回历史数据
- **AND** 响应 SHALL 能表达该能力已 deprecated
- **AND** 响应 MUST NOT 暴露服务器真实路径、对象存储内部 key 或明文凭据

#### Scenario: 新流程不默认创建 SBOM 分析
- **WHEN** 前端执行新迁移流程
- **THEN** 前端和后端 SHALL 默认使用依赖分析节点
- **AND** 后端 MUST NOT 在新流程自动合并、报告或归档中默认创建新的 `SBOM_ANALYSIS` 任务

#### Scenario: 保留历史 SBOM 数据
- **WHEN** 系统升级到依赖分析主流程
- **THEN** 旧 `sbom_*` 表、旧 `SBOM_RESULT` 迁移输入和旧 SBOM artifact SHALL 保留历史兼容
- **AND** 后端 MUST NOT 将新依赖分析结果写入旧 `sbom_*` 表

#### Scenario: SBOM 创建入口兼容策略
- **WHEN** 客户端调用旧 SBOM 创建接口
- **THEN** 后端 SHALL 按配置保留兼容创建或返回明确 deprecated 错误
- **AND** 错误响应 SHALL 说明应使用依赖分析 API
- **AND** 后端 MUST NOT 静默把旧 SBOM 创建请求改写为依赖分析请求
