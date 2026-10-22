## Why

当前 SBOM 分析对目标环境的判断主要依赖已安装软件包、owner package 和仓库候选。若目标 RISC-V 环境通过源码或手工方式安装了同名工具，例如 `/opt/gcc-14/bin/gcc`，该工具可能不会出现在包管理器清单中，导致分析器无法判断目标环境已经具备可执行工具能力。

这会把“目标环境已有同名工具但来源不可追踪”的情况误判为需要仓库安装、人工确认或源码构建。现在需要把 unmanaged/source-built 工具作为目标已安装事实纳入分析，但保持比包管理器安装更高的风险等级。

## What Changes

- 扩展环境采集中的 `TOOL_VERSION` / `TOOL_PROVIDER` 证据：
  - 对 `rpm -qf` / `dpkg-query` 无法归属的软件工具保留工具组件记录。
  - 增加 `installOrigin=package|unmanaged|unknown`、`providerScanner`、`versionMajor`、`versionText`、`toolPath` 等 metadata。
  - 根据 `/usr/local`、`/opt`、用户 `.local` 等路径推断 unmanaged 工具来源。
- 扩展 SBOM 分析器匹配：
  - 目标已安装 tool 优先于目标仓库候选。
  - 同名 tool 可作为 `TARGET_PRESENT` 候选。
  - unmanaged/source-built tool 命中时风险为 `MEDIUM`，不是 `LOW`。
  - 主版本不同的同名工具可被识别为已存在但需要确认兼容性。
- 补充测试覆盖：
  - package-managed tool 正常匹配。
  - unmanaged 同名 tool 匹配。
  - 同名不同主版本工具匹配。
  - 无 ownerPackage 但存在 toolPath/version 的目标工具不应被误判为缺失。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `project-source-environment`: 环境采集需要记录 unmanaged tool 证据和工具安装来源。
- `sbom-analysis-runtime`: SBOM 分析需要支持同名工具版本匹配，并区分 package-managed 与 unmanaged 工具风险。

## Impact

- `backend/src/main/java/cn/rvport/backend/environment/runtime/SshRuntimeService.java`
- `backend/src/test/java/cn/rvport/backend/environment/runtime/SshRuntimeServiceTests.java`
- `tools/sbom-analyzer/sbom_analyzer/engine.py`
- `tools/sbom-analyzer/tests/test_analyzer.py`
- SBOM 分析结果 metadata、风险等级和静态报告展示
