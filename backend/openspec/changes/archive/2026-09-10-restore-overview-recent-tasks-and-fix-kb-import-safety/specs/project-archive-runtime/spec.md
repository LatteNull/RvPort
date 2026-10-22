## MODIFIED Requirements

### Requirement: 归档候选摘要必须保持安全轻量
归档候选 summary SHALL 作为归档列表和归档 manifest 的安全索引摘要使用，不得承载完整报告正文、完整问题明细、原始 evidence、服务器路径、对象存储内部位置或敏感凭据；合法路径字段名和安全项目相对路径不应仅因名称或相对路径形式被拒绝。

#### Scenario: 业务节点登记报告候选
- **WHEN** 业务节点成功生成可归档报告并登记归档候选
- **THEN** 候选 summary SHALL 只包含聚合统计、受控资源 ID、状态、风险摘要和可安全展示的短文本
- **AND** 完整报告内容 SHALL 通过 artifact 引用下载
- **AND** 候选 summary MUST NOT 包含 `locationLabel` 明细列表、完整 `evidence`、完整输入快照、bucket、object key 或服务器真实路径

#### Scenario: 候选摘要包含合法路径结构
- **WHEN** 候选 summary 包含 `path`、`paths`、`filePath` 等字段名，且字段值为空列表、文件名或不含目录穿越的安全项目相对路径
- **THEN** 归档候选服务 SHALL 允许保存该候选
- **AND** 后端 MUST NOT 仅因为字段名包含 `path` 而拒绝候选

#### Scenario: 候选摘要包含危险路径文本
- **WHEN** 候选 summary 中包含服务器绝对路径、`../` 目录穿越、对象存储内部 key、凭据、token 或私钥相关文本
- **THEN** 归档候选服务 SHALL 拒绝保存该候选
- **AND** 调用方 SHALL 将该失败作为候选登记失败处理
- **AND** 调用方 MUST NOT 因候选登记失败泄露被拒绝的敏感文本

#### Scenario: 嵌套候选摘要安全校验
- **WHEN** 合法或危险内容出现在嵌套 object、array 或集合中
- **THEN** 归档候选服务 SHALL 递归执行相同的字段和值安全校验
- **AND** 空 `paths` 数组 SHALL 被视为安全内容

#### Scenario: 归档打包读取候选
- **WHEN** 归档任务读取 active candidates 生成归档详情和归档包
- **THEN** 归档详情 SHALL 使用候选 summary 作为列表摘要
- **AND** 归档包 SHALL 通过 artifact 引用读取完整 HTML、JSON 或 LOG
- **AND** 归档任务 MUST NOT 假设候选 summary 包含完整报告明细
