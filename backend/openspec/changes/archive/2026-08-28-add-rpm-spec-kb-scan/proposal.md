## Why

当前知识库扫描已经覆盖 C/C++ 源码、汇编和部分构建文件，但 RPM 打包项目中的 `*.spec` 文件不会被 scanner 发现和按 RPM spec 语义检测。对于使用 `rpmbuild` 的项目，`%prep`、`%build`、`%install`、`%check` 以及架构条件可能直接决定 RISC-V 迁移是否可构建、可测试，因此需要补齐该输入面。

## What Changes

- KB Scanner 必须发现并扫描 RPM spec 文件。
- RPM spec 检测必须使用单独的 YAML 规则文件承载，不和现有通用 build 规则混写。
- RPM spec 匹配逻辑必须支持对应的匹配规则，覆盖 section、架构条件、架构限制和 x86-only 编译/测试参数。
- `%check` 必须纳入扫描范围，用于发现测试阶段的 x86-only 路径、RISC-V 跳过逻辑和测试阶段架构参数。
- RPM spec 扫描默认基于原始 spec 静态文本和架构相关局部宏识别，不引入完整 RPM 宏展开作为必需流程。
- 扫描结果必须继续进入现有 KB finding、代码上下文、报告下载和归档候选登记链路。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `kb-scan-runtime`: 补充 RPM spec 文件发现、独立 YAML 规则和 RPM spec 语义匹配要求。

## Impact

- 影响 `tools/kb-scanner` 的文件发现、规则匹配和规则集内容。
- 影响 KB 扫描 finding 的规则类型、source kind、evidence 和报告展示数据。
- 需要补充 scanner 单元测试、后端 KB scan 集成测试或 E2E fixture，确保 RPM spec finding 能通过 API 查询和报告下载验证。
