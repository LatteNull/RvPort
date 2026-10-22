## ADDED Requirements

### Requirement: E2E 测试必须覆盖对象存储制品能力
API E2E 测试套件 SHALL 覆盖对象存储连通性、后端输出制品写入、业务下载和清理行为。

#### Scenario: 验证对象存储连通性
- **WHEN** E2E check 运行且对象存储配置启用
- **THEN** 测试 SHALL 验证后端或测试辅助能力可以访问 MinIO
- **AND** 测试 SHALL 验证目标 bucket 可用

#### Scenario: 验证 KB artifact 对象存储
- **WHEN** E2E 运行 KB 扫描并产生 artifact
- **THEN** 测试 SHALL 校验输出制品元数据已写入
- **AND** 测试 SHALL 通过 KB 业务下载接口读取对象内容
- **AND** 响应 MUST NOT 暴露 bucket、object key 或服务器真实路径

#### Scenario: 验证 SBOM artifact 对象存储
- **WHEN** E2E 运行 SBOM 分析并产生 artifact
- **THEN** 测试 SHALL 校验输出制品元数据已写入
- **AND** 测试 SHALL 通过 SBOM 业务接口读取 artifact 内容
- **AND** 响应 MUST NOT 暴露 bucket、object key 或服务器真实路径

#### Scenario: 清理对象存储测试数据
- **WHEN** E2E 清理本次 run id 创建的数据
- **THEN** 清理流程 SHALL 删除对应输出制品元数据
- **AND** 清理流程 SHALL 尽力删除对象存储中的测试对象
