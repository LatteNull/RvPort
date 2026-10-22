## ADDED Requirements

### Requirement: 扫描器依赖必须在容器内安装和验证
KB Scanner 的 Python、原生解析器和测试依赖 SHALL 在容器镜像构建过程中安装并锁定，正式构建和验证流程 MUST NOT 要求修改开发者宿主机的 Python 或系统工具环境。

#### Scenario: 开发者构建扫描器测试环境
- **WHEN** 开发者需要安装或更新 Tree-sitter、LLVM/Clang、图存储或模型校验依赖
- **THEN** 依赖 SHALL 通过 Docker build stage 安装
- **AND** 开发者宿主机 MUST NOT 执行对应的 pip、npm 或系统包安装命令

#### Scenario: 宿主机没有分析器依赖
- **WHEN** 宿主机仅安装受支持的容器构建和运行工具
- **THEN** 开发者 SHALL 仍能构建并运行 KB Scanner 的正式测试环境

### Requirement: 项目必须提供独立的 kb-scanner-test 容器
项目 SHALL 在 `tools/kb-scanner/Dockerfile.test` 提供名为 `kb-scanner-test` 的独立 image target。项目 SHALL 通过专属 `tools/kb-scanner/compose.test.yml` 将该镜像作为一次性测试容器运行，而 MUST NOT 将测试服务合并到现有根 Compose，也 MUST NOT 为此修改 `backend/Dockerfile` 或生产镜像。

#### Scenario: 运行默认容器测试
- **WHEN** 开发者使用专属 Compose 文件启动 `kb-scanner-test` 容器
- **THEN** 容器 SHALL 运行现有 KB Scanner 单元测试和兼容契约测试后退出
- **AND** 任一必需测试失败 SHALL 产生非零容器退出码

#### Scenario: 独立管理测试生命周期
- **WHEN** 开发者构建、启动、停止或清理 `kb-scanner-test`
- **THEN** 操作 SHALL 只作用于专属测试 Compose project 及其临时资源
- **AND** 现有 Compose 中的 API、worker、数据库、消息队列、缓存和对象存储服务 SHALL 保持不变

#### Scenario: 测试容器保持运行隔离
- **WHEN** `kb-scanner-test` 容器启动
- **THEN** 它 MUST NOT 依赖或加入现有 Compose 的网络和业务卷
- **AND** 它 MUST NOT 获得现有服务的数据库、消息队列、缓存或对象存储凭据

#### Scenario: 验证技术候选
- **WHEN** change 增加 Tree-sitter/Clang、GraphStore、构建解析或 RPM 安全 spike
- **THEN** 对应测试 SHALL 在独立的 `kb-scanner-test` 容器或由其复用的容器依赖环境中执行
- **AND** 选型证据 MUST NOT 依赖宿主机已安装的同名包或命令

### Requirement: 测试依赖必须可复现
`kb-scanner-test` SHALL 从锁定文件和固定原生包版本获得候选 scanner runtime 依赖；测试专用依赖 MAY 在独立层叠加，但 MUST NOT 替代或改变已锁定的 runtime 候选版本。

#### Scenario: 更新扫描器依赖
- **WHEN** 任一扫描器候选依赖版本发生变化
- **THEN** `kb-scanner-test` SHALL 在相同版本上重新运行
- **AND** 版本变更 SHALL 记录兼容性、安全性和许可证影响

#### Scenario: 候选技术进入生产
- **WHEN** 后续工作准备把已验证候选加入生产 worker
- **THEN** 该生产接入 SHALL 由独立 change 定义和验证
- **AND** 本 change 的测试 Dockerfile MUST NOT 被视为生产镜像定义

### Requirement: 容器化不得放宽不可信代码执行边界
即使分析依赖已安装在容器内，默认 KB Scan 仍 MUST NOT 执行不可信项目中的 Make、M4、RPM、CMake、编译器插件或其他任意命令路径。

#### Scenario: 扫描包含命令执行构造的项目
- **WHEN** Makefile、Autoconf、RPM spec、CMake 或 compilation database 包含可能执行外部代码的构造
- **THEN** scanner SHALL 将其作为静态 Evidence、unsupported expression 或 diagnostic 处理
- **AND** scanner MUST NOT 执行该构造

#### Scenario: 未来需要完整求值
- **WHEN** 后续能力必须执行项目配置或宏求值才能获得结果
- **THEN** 该能力 SHALL 由独立 change 定义无业务凭据、受限网络、只读输入和资源限制的一次性沙箱
- **AND** 普通容器本身 MUST NOT 被视为充分的执行隔离
