## Why

当前 SBOM 分析对 `.so` 和 native 文件主要依赖文件名或仓库清单做弱匹配，无法稳定判断源侧库文件实际由哪个包提供，也无法在目标 RISC-V 仓库中基于 provider 证据查找替代包。RISC-V 仓库 metadata 未刷新、x86 源侧缺少 provider 归属、架构相关名称未归一化，会导致可替代组件被误判为需要源码构建或人工确认。

## What Changes

- 增强环境采集脚本，在 x86 源环境和 RISC-V 目标环境中都采集 `.so` / native 文件的 provider/owner package 信息。
- 在 RISC-V 目标环境仓库采集前执行受控 metadata refresh 或 metadata 可用性检查，并记录 refresh 状态与警告。
- 为 `.so` 文件名、路径和包名增加架构归一化候选生成，用于把 x86/amd64 命名转换为 RISC-V 查询候选。
- 扩展 SBOM 分析器输入和匹配逻辑，优先使用 provider/owner package、normalized name、whatprovides 证据和 confidence 生成替代候选。
- 保持基础环境快照可用：仓库 metadata refresh 或 provides 查询失败时记录 warning，不阻断已安装包、工具版本和基础组件快照。
- 补充 Java 单元测试、分析器测试和 API E2E，覆盖正常流程、异常流程和 edge case。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `project-source-environment`: 环境采集需要同时采集 x86 与 RISC-V 的库 provider 信息、受控刷新仓库 metadata，并保存 provider/normalization 证据。
- `sbom-analysis-runtime`: SBOM 分析需要基于 provider、whatprovides、架构归一化候选和 confidence 进行替代判断。

## Impact

- 影响 `SshRuntimeService` 的 `ENV_COLLECT` 内置脚本、解析逻辑和 `environment_components` 写入元数据。
- 影响 `tools/sbom-analyzer` 的输入 schema、匹配策略、候选证据和输出结果。
- 可能影响 `SbomAnalysisRuntimeService` 的 analyzer input 导出和结果导入。
- 需要扩展测试覆盖真实包归属、仓库 metadata 过期、provider 查询缺失、架构名称归一化和敏感信息脱敏。
