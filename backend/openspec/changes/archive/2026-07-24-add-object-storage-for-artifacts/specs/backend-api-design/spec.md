## MODIFIED Requirements

### Requirement: API 不引入通用 Artifact 资源
MVP API 设计 SHALL NOT 引入面向前端的通用 Artifact API，下载能力 SHALL 由报告、归档、KB、SBOM 和日志等业务资源提供。后端 MAY 使用统一输出制品元数据和对象存储作为业务下载接口的内部实现。

#### Scenario: 下载报告
- **WHEN** 前端下载 HTML 或 JSON 报告
- **THEN** API SHALL 通过报告资源的受控下载接口提供文件
- **AND** SHALL NOT 要求前端调用通用 artifact 资源
- **AND** API MUST NOT 暴露对象存储 bucket、object key 或服务器真实路径

#### Scenario: 下载归档包
- **WHEN** 前端下载项目归档包
- **THEN** API SHALL 通过归档资源的受控下载接口提供文件
- **AND** SHALL NOT 暴露服务器真实路径、对象存储 bucket 或 object key

#### Scenario: 下载任务日志
- **WHEN** 前端下载任务日志
- **THEN** API SHALL 通过任务日志资源的受控下载接口提供文件
- **AND** SHALL NOT 暴露服务器真实路径、对象存储 bucket 或 object key

#### Scenario: 下载 KB 或 SBOM 输出制品
- **WHEN** 前端下载或查询 KB/SBOM 业务输出制品
- **THEN** API SHALL 继续通过 KB/SBOM 业务接口提供能力
- **AND** 前端 MUST NOT 依赖通用 artifact API

## ADDED Requirements

### Requirement: API 响应必须隐藏对象存储内部位置
业务 API SHALL 在使用对象存储保存输出制品时隐藏内部存储位置。

#### Scenario: 返回 artifact 摘要
- **WHEN** API 返回报告、KB、SBOM、归档或日志制品摘要
- **THEN** 响应 MAY 包含 artifact ID、artifact type、content type、size bytes、sha256、created at 和安全 summary
- **AND** 响应 MUST NOT 包含 bucket、object key、endpoint、access key、secret key 或服务器真实路径

#### Scenario: 下载对象存储制品
- **WHEN** 用户通过业务下载接口下载对象存储中的制品
- **THEN** 后端 SHALL 先执行对应业务资源的项目访问权限校验
- **AND** 后端 SHALL 代理读取对象并返回内容
- **AND** 后端 MUST NOT 将 MinIO 预签名 URL 作为 MVP 默认下载方式返回给前端
