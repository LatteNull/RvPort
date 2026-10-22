## ADDED Requirements

### Requirement: 后端构建必须支持 test-support 源码排除
后端 Maven 构建 SHALL 支持默认生产构建排除 test-support 源码，并 SHALL 支持显式 test-support 构建。

#### Scenario: 默认构建排除 test-support
- **WHEN** 开发者执行默认 `mvn package`
- **THEN** Maven SHALL NOT 编译 test-support 源码目录
- **AND** jar 中 MUST NOT 包含 test-support API 类或资源

#### Scenario: 显式构建包含 test-support
- **WHEN** 开发者执行带 test-support profile 的 Maven 构建或运行命令
- **THEN** Maven SHALL 编译 test-support 源码目录
- **AND** 后端 SHALL 能加载 test-support API 相关 bean

#### Scenario: 文档说明构建差异
- **WHEN** 开发者查看后端启动和构建文档
- **THEN** 文档 SHALL 明确区分生产构建命令和 E2E/test-support 构建命令

### Requirement: 后端生产安全配置不得依赖旧 dev session
后端默认生产源码和安全配置 SHALL 不再暴露 `/api/dev/session`。

#### Scenario: 默认生产运行
- **WHEN** 后端以默认生产构建启动
- **THEN** `/api/dev/session` SHALL 不可访问
- **AND** 安全配置 MUST NOT 对 `/api/dev/session` 配置 permit-all

#### Scenario: E2E 需要创建 session
- **WHEN** E2E 需要绕过交互式登录创建测试 session
- **THEN** E2E SHALL 使用 `/api/test-support/session`
