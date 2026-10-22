## ADDED Requirements

### Requirement: 环境采集必须显式处理采集辅助工具缺失
环境采集 SHALL 在源环境和目标环境中检测采集辅助工具可用性，并 SHALL 在工具缺失、安装失败或降级采集时记录可审计的 warning。

#### Scenario: 采集前检测源环境辅助工具
- **WHEN** worker 在源环境执行依赖分析前环境刷新或环境采集
- **THEN** 后端 SHALL 检测 `find`、`readelf`、`objdump`、`rpm` 或对应包管理器查询工具是否可用
- **AND** 后端 SHALL 检测构建观测所需的 `strace` 和 `bear` 是否可用
- **AND** 检测结果 SHALL 写入采集日志或快照 raw summary

#### Scenario: 采集前检测目标环境辅助工具
- **WHEN** worker 在目标环境执行依赖分析前环境刷新或环境采集
- **THEN** 后端 SHALL 检测 `find`、`readelf`、`objdump`、`rpm` 或对应包管理器查询工具是否可用
- **AND** 后端 MUST NOT 要求目标环境安装 `strace` 或 `bear` 才能完成基础 provider 采集
- **AND** 检测结果 SHALL 写入采集日志或快照 raw summary

#### Scenario: 工具缺失时记录 warning
- **WHEN** 远程环境缺少采集辅助工具且无法补齐
- **THEN** 环境快照 raw summary SHALL 包含明确的 `PARSE_WARNING`
- **AND** warning SHALL 指明缺失工具名和受影响的采集范围
- **AND** 后端 MUST NOT 静默产生空的库文件清单并把它解释为目标环境没有库

### Requirement: 环境采集必须受控尝试安装缺失辅助工具
依赖分析触发的环境刷新 SHALL 在源环境和目标环境中对缺失的采集辅助工具执行受控自动安装尝试，并 SHALL 保持安装范围可预测、可审计。

#### Scenario: 源环境补齐构建观测工具
- **WHEN** 依赖分析前刷新源环境且检测到 `find`、`readelf`、`objdump`、`strace` 或 `bear` 缺失
- **THEN** 后端 SHALL 根据包管理器能力尝试安装固定 allowlist 中的 `findutils`、`binutils`、`strace` 和 `bear`
- **AND** 安装命令、成功或失败摘要 SHALL 写入任务日志或快照 warning
- **AND** 安装失败时后端 SHALL 继续使用已有构建日志、已有 compile database 或其他可用证据完成分析

#### Scenario: 目标环境补齐 provider 采集工具
- **WHEN** 依赖分析前刷新目标环境且检测到 `find`、`readelf` 或 `objdump` 缺失
- **THEN** 后端 SHALL 根据包管理器能力尝试安装固定 allowlist 中的 `findutils` 和 `binutils`
- **AND** 安装命令、成功或失败摘要 SHALL 写入任务日志或快照 warning
- **AND** 安装失败时后端 SHALL 继续保存已安装包、仓库包和其他可用 provider 证据

#### Scenario: 非支持包管理器环境
- **WHEN** 远程环境缺少辅助工具且后端无法识别可支持的安装命令
- **THEN** 后端 SHALL 跳过自动安装
- **AND** 快照 SHALL 记录自动安装不可用的 warning
- **AND** 后端 MUST NOT 执行非 allowlist 的任意安装命令

### Requirement: 库文件采集必须具备标准目录降级扫描
环境采集 SHALL 在标准库目录中采集 `.so`、版本化 `.so` 和相关符号链接，并 SHALL 在 `find` 不可用时使用降级策略保留基础库证据。

#### Scenario: find 可用时完整扫描标准库目录
- **WHEN** 远程环境存在 `find`
- **THEN** 后端 SHALL 扫描 `/lib`、`/lib64`、`/usr/lib`、`/usr/lib64`、`/usr/local/lib` 中的 `.so` 文件
- **AND** 后端 SHALL 为可归属文件记录 owner package、owner version、owner arch 和 provider scanner

#### Scenario: find 不可用时降级扫描标准库目录
- **WHEN** 远程环境缺少 `find`
- **THEN** 后端 SHALL 使用 shell glob 或等价固定深度策略扫描标准库目录中常见 `.so` 文件
- **AND** 对发现的文件仍 SHALL 尝试执行 owner package 查询
- **AND** 快照 SHALL 记录本次使用了降级扫描

#### Scenario: 标准库符号链接目录
- **WHEN** `/lib64` 或其他标准库目录是指向 `/usr/lib64` 的符号链接
- **THEN** 后端 SHALL 保证实际库文件或符号链接路径至少有一类路径被采集
- **AND** 后端 MUST NOT 因目录是符号链接而完全跳过基础库文件
