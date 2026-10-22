## ADDED Requirements

### Requirement: 后端必须提供对象存储客户端抽象
后端 SHALL 提供 S3 兼容对象存储客户端抽象，用于保存和读取后端运行产生的输出制品。

#### Scenario: 上传对象
- **WHEN** 业务模块需要保存报告、扫描输出、日志归档或归档包
- **THEN** 后端 SHALL 通过统一对象存储服务上传对象
- **AND** 对象 SHALL 保存到配置指定的 bucket
- **AND** 上传结果 SHALL 包含 bucket、object key、content type、size bytes 和 sha256

#### Scenario: 读取对象
- **WHEN** 业务下载接口需要返回已保存制品
- **THEN** 后端 SHALL 通过统一对象存储服务读取对象内容
- **AND** 后端 SHALL 在业务权限校验通过后才读取对象

#### Scenario: 对象不存在
- **WHEN** 元数据存在但对象存储中对象不存在
- **THEN** 后端 SHALL 返回安全业务错误
- **AND** 后端 MUST NOT 暴露 bucket 内部结构、secret key 或底层异常细节

### Requirement: 后端生成制品必须保存统一元数据
后端 SHALL 使用统一元数据记录描述后端运行产生的输出制品，使数据库无需保存大文件内容。

#### Scenario: 保存输出制品元数据
- **WHEN** 后端成功保存一个输出制品到对象存储
- **THEN** 后端 SHALL 写入 `stored_artifacts` 或等效元数据记录
- **AND** 元数据 SHALL 包含 `project_id`、`task_id`、`owner_type`、`owner_id`、`artifact_type`、`bucket`、`object_key`、`content_type`、`size_bytes`、`sha256`、`summary` 和 `created_at`
- **AND** API 响应 MUST NOT 返回 `bucket`、`object_key` 或服务器真实路径

#### Scenario: 限制制品归属类型
- **WHEN** 后端写入输出制品元数据
- **THEN** `owner_type` SHALL 使用稳定枚举值
- **AND** `owner_type` SHALL 至少支持 `KB_SCAN`、`SBOM_ANALYSIS`、`MIGRATION_REPORT` 和 `ARCHIVE`
- **AND** 后端 MUST NOT 将源码包、源码工作副本或 Git checkout 作为 `stored_artifacts` 记录保存

#### Scenario: 防止重复制品
- **WHEN** 同一业务 owner 下同一 artifact type 不应重复
- **THEN** 数据库 SHALL 能通过 `owner_type + owner_id + artifact_type` 或等效约束防止不可解释的重复成功记录

### Requirement: 对象 key 必须安全构造
后端 SHALL 使用安全规则构造对象存储 key，避免泄露服务器路径或用户提交的路径片段。

#### Scenario: 生成对象 key
- **WHEN** 后端为输出制品生成 object key
- **THEN** object key SHALL 基于项目 ID、owner type、owner ID、artifact type 和 artifact ID 构造
- **AND** object key MUST NOT 包含服务器绝对路径
- **AND** object key MUST NOT 直接拼接用户提交的路径字符串

#### Scenario: 下载文件名
- **WHEN** 后端通过业务接口下载对象存储中的制品
- **THEN** 响应文件名 SHALL 使用业务层生成的安全文件名
- **AND** 响应头 MUST NOT 暴露 object key

### Requirement: 对象存储写入必须保持元数据一致性
后端 SHALL 避免写入指向不存在对象的成功元数据，并 SHALL 对事务失败后的对象执行尽力清理。

#### Scenario: 对象上传失败
- **WHEN** 对象存储上传失败
- **THEN** 后端 MUST NOT 写入成功态 artifact 元数据
- **AND** 调用方 SHALL 收到可处理的业务异常

#### Scenario: 元数据写入失败
- **WHEN** 对象上传成功但数据库元数据写入失败
- **THEN** 后端 SHALL 尽力删除刚上传的对象
- **AND** 后端 SHALL 将本次保存视为失败

#### Scenario: 删除制品
- **WHEN** E2E 清理或业务清理删除某个输出制品
- **THEN** 后端 SHALL 删除对应元数据
- **AND** 后端 SHALL 尽力删除对象存储中的对象
