## ADDED Requirements

### Requirement: API E2E 必须覆盖极简 RPM 环境的 provider 匹配
API E2E 依赖分析模块 SHALL 覆盖源环境和目标环境为 RPM/DNF 系统时，辅助工具缺失、自动安装尝试、库文件降级采集和 provider package 回退匹配。

#### Scenario: 极简目标环境基础库不误判缺失
- **WHEN** E2E 使用目标环境中安装了 `glibc`、`libgcc` 但缺少 `findutils` 或 `binutils` 的 RPM/DNF 环境运行依赖分析
- **THEN** 后端 SHALL 在分析前尝试补齐目标环境采集工具
- **AND** 依赖分析结果 MUST NOT 将 `libc.so` 或 `libgcc_s.so` 误判为缺失
- **AND** 结果 SHALL 包含目标 provider package/version 或说明可用的回退证据

#### Scenario: 源环境构建观测工具补齐
- **WHEN** E2E 使用源环境运行 source-only 构建和依赖分析
- **THEN** 后端 SHALL 尝试补齐源环境中的 `strace` 和 `bear`
- **AND** 测试 SHALL 验证任务日志或 artifact 中存在 execve 观测、compile database 证据或明确的工具缺失 warning

#### Scenario: 自动安装失败不导致静默误判
- **WHEN** E2E 或测试 fixture 模拟辅助工具安装失败
- **THEN** 环境刷新或依赖分析 SHALL 记录安装失败 warning
- **AND** 后端 SHALL 使用已有包清单和 provider package 回退继续生成可审计结果
- **AND** 结果 MUST NOT 因空的库扫描结果直接断定目标环境完全没有基础库

#### Scenario: 源 owner package 回退匹配
- **WHEN** E2E 构造或运行包含 `-lc` 和 `-lgcc_s` 的真实构建
- **AND** 目标环境缺少对应 `INSTALLED_LIBRARY` 快照组件但存在 `glibc`、`gcc` 或 `libgcc` package 证据
- **THEN** 依赖分析 SHALL 通过源 owner package 或基础库别名命中目标 provider
- **AND** 测试 SHALL 校验风险等级与 provider version status 一致
