## Why

当前构建驱动依赖分析仍会把编译宏、编译参数探测等内容作为依赖结果展示，导致结果焦点偏离“迁移时目标环境是否具备等价依赖”。同时 ELF/SO 结果只展示源机器使用的库文件，没有把源机器提供这些文件的软件包版本、目标机器或目标软件源中的对应软件包版本串起来，无法判断真实替代风险。

本次变更需要把依赖分析收敛到软件包、工具、库和头文件等可迁移依赖上，并增强 ELF/SO 到源/目标 provider package 的版本匹配。

## What Changes

- 依赖分析结果不再生成或展示 compiler flag、宏、`compile_commands.json`、`build.ninja` 等构建元数据本身的结果项；这些内容只能作为内部 evidence 或日志保留。
- ELF/SO 依赖结果必须优先解析源环境 owner package 和版本，并与目标环境已安装包、软件源包、provides/whatprovides 结果进行匹配。
- ELF/SO 结果必须按用户确认的五类场景映射风险等级：
  - 源机器有对应软件包，目标机器或目标源有对应软件包，并且大版本一致：`INFO`
  - 源机器有对应软件包，目标机器或目标源有对应软件包，目标版本高于源版本：`LOW`
  - 源机器有对应软件包，目标机器或目标源有对应软件包，目标版本低于源版本：`HIGH`
  - 源机器没有对应软件包，但能从文件名、SONAME、readelf 或路径等证据检测到对应软件/库版本，目标机器或目标源有对应软件包版本：`MEDIUM`
  - 源机器没有对应软件包，且无法检测到目标机器或目标源有对应版本：`CRITICAL`
- 依赖结果需要保存源侧 provider、目标侧 provider、版本关系、风险规则和匹配证据，支持列表、详情、HTML/JSON 报告和迁移输入展示。
- 同一个源 provider package 因多个 ELF/SO 文件产生重复命中时需要聚合或去重，列表展示以“软件包/目标 provider/版本关系”为主，保留文件路径证据供详情审计。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `dependency-analysis-runtime`: 调整依赖分析结果范围，移除 flag/macro 类结果项，并增加 ELF/SO provider package 版本匹配规则和风险映射。
- `api-e2e-test-suite`: 增加依赖分析 E2E 对 flag/macro 结果排除、ELF/SO 源/目标 provider 匹配、风险等级映射和去重聚合的验证。

## Impact

- 影响依赖分析 worker、依赖事实提取、目标能力匹配、结果持久化、结果详情、HTML/JSON 制品生成和迁移输入导入展示。
- 可能需要扩展依赖分析结果 evidence JSON 字段内容，但不应把完整日志、服务器真实路径或凭据写入响应。
- 影响真实验证脚本和轻量 HTML 汇总脚本：结果展示应从 raw ELF/SO 列表调整为 provider package 版本匹配列表。
