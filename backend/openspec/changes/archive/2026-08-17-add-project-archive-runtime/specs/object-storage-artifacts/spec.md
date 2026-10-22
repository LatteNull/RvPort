## ADDED Requirements

### Requirement: 对象存储必须保存项目归档包
后端输出制品存储 SHALL 支持保存项目归档包，并 SHALL 通过归档业务接口提供下载。

#### Scenario: 保存归档包制品
- **WHEN** 归档任务成功生成压缩包
- **THEN** 后端 SHALL 将压缩包保存为 `stored_artifacts`
- **AND** `owner_type` SHALL 为 `ARCHIVE`
- **AND** `owner_id` SHALL 为 `archives.id`
- **AND** `artifact_type` SHALL 表达归档包格式

#### Scenario: 归档包制品摘要
- **WHEN** 后端保存归档包制品元数据
- **THEN** `summary` SHALL 包含归档项数量、包含格式、源码版本 ID、归档生成时间和安全文件名摘要
- **AND** `summary` MUST NOT 包含明文凭据、对象存储 object key、服务器真实路径、完整报告正文或完整日志正文

#### Scenario: 下载归档包
- **WHEN** 用户通过归档下载 API 下载归档包
- **THEN** 后端 SHALL 从对象存储读取对应 `ARCHIVE` 制品
- **AND** API 响应 MUST NOT 暴露 bucket、object key 或服务器真实路径
