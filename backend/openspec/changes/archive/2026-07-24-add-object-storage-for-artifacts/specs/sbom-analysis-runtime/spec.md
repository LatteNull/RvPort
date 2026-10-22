## ADDED Requirements

### Requirement: SBOM 分析 artifact 必须支持对象存储
SBOM 分析运行时 SHALL 支持将新生成的分析输出制品保存到对象存储，并 SHALL 保持现有 SBOM artifact 查询接口语义。

#### Scenario: 保存 SBOM 输出到对象存储
- **WHEN** SBOM 分析生成审计摘要、分析器输入摘要或分析器输出摘要 artifact
- **THEN** 后端 SHALL 能将 artifact 内容保存到对象存储
- **AND** 后端 SHALL 保存输出制品元数据
- **AND** 元数据 SHALL 关联 `project_id`、`task_id` 和 `sbom_run_id`

#### Scenario: 查询 SBOM artifact 摘要
- **WHEN** 用户查询 SBOM artifact 列表
- **THEN** 后端 SHALL 返回业务需要的 artifact metadata 和 summary
- **AND** 响应 MUST NOT 返回对象存储 bucket、object key 或服务器真实路径

#### Scenario: 查询 SBOM artifact 内容
- **WHEN** 用户查询某个 SBOM artifact 内容
- **THEN** 后端 SHALL 校验用户对分析所属项目有访问权限
- **AND** 后端 SHALL 从对象存储或兼容的历史 JSON 内容读取 artifact 内容
- **AND** 后端 MUST NOT 暴露对象存储内部位置
