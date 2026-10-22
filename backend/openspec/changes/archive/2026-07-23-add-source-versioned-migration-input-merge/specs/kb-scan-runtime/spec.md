## ADDED Requirements

### Requirement: KB findings 必须可加入迁移输入
KB 扫描结果 SHALL 能作为迁移输入 reference 的代码类来源，并 SHALL 保持源码版本一致性。

#### Scenario: KB finding 导入迁移输入
- **WHEN** 用户将 KB finding 加入迁移输入
- **THEN** 后端 SHALL 校验 finding 属于当前项目
- **AND** 后端 SHALL 校验 finding 的 `source_revision_id` 等于迁移输入 URL 中的 `sourceRevisionId`
- **AND** 后端 SHALL 使用 finding 的 title 生成 `issueTitle`
- **AND** 后端 SHALL 使用 finding 的 severity 生成 `detectedLevel`

#### Scenario: KB finding location label
- **WHEN** 后端为 KB finding 创建迁移输入 reference
- **THEN** `locationLabel` SHALL 使用 finding 的相对 `file_path` 和行号生成
- **AND** 单行 SHALL 表达为 `path:line`
- **AND** 行范围 SHALL 表达为 `path:start-end`
- **AND** 无行号时 SHALL 只使用相对路径

#### Scenario: 跨源码版本 finding 被拒绝
- **WHEN** 用户尝试把源码版本 A 的 finding 导入源码版本 B 的迁移输入
- **THEN** 后端 SHALL 拒绝请求
- **AND** 后端 MUST NOT 创建迁移输入 reference
