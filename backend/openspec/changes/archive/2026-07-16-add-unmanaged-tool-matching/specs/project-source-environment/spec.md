## ADDED Requirements

### Requirement: 环境采集必须记录 unmanaged 工具证据
环境采集 SHALL 对 PATH 可见的基础工具记录可执行事实，并在包管理器无法归属工具路径时保留 unmanaged 或 unknown 安装来源 metadata。

#### Scenario: package-managed 工具
- **WHEN** worker 执行 `ENV_COLLECT`
- **AND** 工具命令可通过 `command -v` 找到
- **AND** `rpm -qf`、`dpkg-query -S` 或等效 provider 查询能找到 owner package
- **THEN** 后端 SHALL 写入 `TOOL` 组件
- **AND** 组件 metadata SHALL 包含 `toolPath`、`ownerPackage`、`ownerVersion`、`ownerArch`、`providerScanner`
- **AND** 组件 metadata SHALL 包含 `installOrigin=package`
- **AND** 组件 metadata SHALL 包含 `versionText` 和可解析时的 `versionMajor`

#### Scenario: unmanaged 工具
- **WHEN** worker 执行 `ENV_COLLECT`
- **AND** 工具命令可通过 `command -v` 找到
- **AND** provider 查询无法找到 owner package
- **AND** 工具真实路径位于 `/usr/local`、`/opt`、`/home/*/.local` 或 `/root/.local`
- **THEN** 后端 SHALL 写入 `TOOL` 组件
- **AND** 组件 metadata SHALL 包含 `toolPath`
- **AND** 组件 metadata SHALL 包含 `installOrigin=unmanaged`
- **AND** 组件 metadata SHALL 包含 `providerScanner=none`
- **AND** 组件 metadata SHALL 包含 `versionText` 和可解析时的 `versionMajor`
- **AND** 后端 MUST NOT 因 owner package 为空而丢弃该工具组件

#### Scenario: unknown 来源工具
- **WHEN** worker 执行 `ENV_COLLECT`
- **AND** 工具命令可通过 `command -v` 找到
- **AND** provider 查询无法找到 owner package
- **AND** 工具路径不满足 unmanaged 路径规则
- **THEN** 后端 SHALL 写入 `TOOL` 组件
- **AND** 组件 metadata SHALL 包含 `installOrigin=unknown`
- **AND** 组件 metadata SHALL 包含 `providerScanner=none`
- **AND** 后端 SHALL 保留 `toolPath`、`versionText` 和可解析时的 `versionMajor`

#### Scenario: 工具不在 PATH
- **WHEN** 某个源码安装工具存在于远程文件系统但不在当前 PATH
- **THEN** 默认环境采集 MAY 不记录该工具
- **AND** 后端 MUST NOT 扫描用户 home、`/opt` 或 `/usr/local` 的全部可执行文件
- **AND** 后端 SHALL 仅基于已发现的 PATH 可见工具生成 `TOOL` 组件
