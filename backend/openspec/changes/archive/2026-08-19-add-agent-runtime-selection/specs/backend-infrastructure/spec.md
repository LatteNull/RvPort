## ADDED Requirements

### Requirement: 后端容器必须支持多 Agent Runtime
后端 Docker 构建 SHALL 支持 Codex、DeepSeek Harness 和 OpenCode 三类 agent runtime 的可执行入口，使测试结果比较可以在容器内运行选定 agent。

#### Scenario: 构建包含 Codex runtime
- **WHEN** 构建后端 Docker 镜像
- **THEN** 镜像 SHALL 提供 Codex CLI 可执行入口或明确的安装失败诊断
- **AND** 默认 Codex runtime executable SHALL 可通过环境变量覆盖

#### Scenario: 构建包含 DeepSeek Harness runtime
- **WHEN** 构建后端 Docker 镜像
- **THEN** 镜像 SHALL 提供 DeepSeek Harness 可执行入口或明确的安装失败诊断
- **AND** DeepSeek Harness runtime executable SHALL 可通过环境变量覆盖

#### Scenario: 构建包含 OpenCode runtime
- **WHEN** 构建后端 Docker 镜像
- **THEN** 镜像 SHALL 提供 OpenCode 可执行入口或明确的安装失败诊断
- **AND** OpenCode runtime executable SHALL 可通过环境变量覆盖

#### Scenario: Runtime 不可用
- **WHEN** 容器内某个 agent 可执行文件不存在或无法运行
- **THEN** 后端 SHALL 在 agent runtime 探测中返回不可用状态
- **AND** 后端 MUST NOT 在应用启动时因为某个非默认 agent 缺失而整体启动失败

#### Scenario: Maven 依赖缓存不受 agent 安装影响
- **WHEN** 后端 Docker 构建安装 agent CLI
- **THEN** 构建过程 SHALL 继续使用已有 Maven 依赖缓存策略
- **AND** agent 安装层 SHOULD 与 Maven 依赖下载层解耦，减少无关变更导致的重复下载
