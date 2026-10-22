## ADDED Requirements

### Requirement: 对象存储必须支持构建上下文制品
后端输出制品存储 SHALL 支持保存构建验证产生的 compile database 构建上下文制品。

#### Scenario: 保存构建上下文制品
- **WHEN** 构建验证 worker 保存 `compile_commands.json`
- **THEN** 后端 SHALL 使用 `stored_artifacts` 保存制品元数据
- **AND** `owner_type` SHALL 支持 `BUILD_VALIDATION`
- **AND** `owner_id` SHALL 指向 `build_runs.id`
- **AND** `artifact_type` SHALL 使用稳定值表示 compile database JSON

#### Scenario: 构建上下文制品摘要安全
- **WHEN** 后端保存构建上下文制品元数据
- **THEN** `summary` SHALL 包含 sha256、size bytes、command count、source revision ID、environment ID 和 build scope
- **AND** `summary` MUST NOT 包含完整 `compile_commands.json`、服务器真实路径、远端工作目录、bucket、object key 或明文凭据

#### Scenario: 业务内读取构建上下文
- **WHEN** KB 扫描运行时需要读取构建上下文制品
- **THEN** 后端 SHALL 通过 stored artifact ID 在服务端内部读取对象内容
- **AND** 读取前 SHALL 校验构建运行和 KB 扫描属于同一项目和源码版本
- **AND** 后端 MUST NOT 提供绕过业务权限的通用 artifact 读取路径
