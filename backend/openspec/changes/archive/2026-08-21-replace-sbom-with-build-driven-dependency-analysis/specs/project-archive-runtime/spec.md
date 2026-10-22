## ADDED Requirements

### Requirement: 归档必须支持依赖分析候选
项目归档运行时 SHALL 支持归档当前源码版本下的依赖分析报告和结果摘要，并 SHALL 保留历史 SBOM 归档项兼容。

#### Scenario: 登记依赖分析归档候选
- **WHEN** 依赖分析成功生成 HTML、JSON 或摘要制品
- **THEN** 后端 SHALL 为当前 `sourceRevisionId` 登记归档候选
- **AND** 候选的 `nodeType` 或等效字段 SHALL 表达依赖分析节点
- **AND** 候选 SHALL 关联依赖分析运行、任务和制品引用

#### Scenario: 归档当前状态包含依赖分析
- **WHEN** 用户归档当前状态且当前源码版本存在 active 依赖分析候选
- **THEN** 归档 SHALL 固化依赖分析报告、JSON 摘要和结果统计
- **AND** 归档详情和下载包 MUST NOT 暴露对象存储内部 key 或服务器真实路径

#### Scenario: 历史 SBOM 归档兼容
- **WHEN** 用户查看包含 SBOM 归档项的历史归档
- **THEN** 后端 SHALL 继续展示和下载历史 SBOM 归档项
- **AND** 新归档默认 SHALL 使用依赖分析候选而不是 SBOM 候选
