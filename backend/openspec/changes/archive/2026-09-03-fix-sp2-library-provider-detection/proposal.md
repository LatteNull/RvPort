## Why

在 openEuler 24.03 LTS-SP2 RISC-V 极简容器中，`libc.so`、`libgcc_s.so` 等基础库实际由 `glibc`、`libgcc/gcc` 提供，但依赖分析结果仍可能显示为缺失。当前问题会把目标环境能力误判为不可用，影响依赖分析、报告和后续自动修复判断。

## What Changes

- 环境采集需要显式识别源环境和目标环境中的 `find`、`readelf`、`objdump` 等采集辅助工具缺失，并将缺失情况写入快照 warning，而不是静默产生空的库文件清单。
- 依赖分析前刷新源环境和目标环境时，如果发现采集辅助工具缺失，后端需要按包管理器能力进行受控自动安装尝试，安装失败时记录 warning 并继续使用可获得的证据。
- 源环境还需要在构建观测前尝试补齐 `strace` 和 `bear`，用于稳定产出 execve 观测和 `compile_commands.json`，安装失败时必须记录 warning 并允许后续分析使用已有日志证据。
- 环境采集在标准库目录扫描时需要具备降级策略，避免极简系统缺少 `find` 时完全丢失 `/lib64`、`/usr/lib64` 等目录下的 `.so` 证据。
- 依赖分析对 `compile_commands.json`、`strace execve`、linker flag 解析出来的 `-lc`、`-lgcc_s` 等链接库，需要复用 provider-aware 匹配逻辑。
- 当源侧已确认 owner package 时，目标侧库文件未采集或未命中时，必须回退到目标环境同名包、规范化包名或库别名包进行匹配。
- `libc -> glibc`、`libgcc_s -> gcc/libgcc` 等基础库别名需要在链接库 provider 匹配中稳定生效。
- 增加针对极简 openEuler/RPM 环境的单元测试和 E2E 覆盖，验证目标环境存在包但库扫描不完整时不会误判缺失。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `project-source-environment`: 环境采集需要对辅助工具缺失、库文件扫描降级和 provider 证据完整性提出更明确要求。
- `dependency-analysis-runtime`: 依赖分析需要对链接库使用源侧 owner package 到目标侧 provider package 的回退匹配，避免基础库误判缺失。
- `api-e2e-test-suite`: E2E 需要覆盖极简 RPM/openEuler 目标环境中基础库 provider 匹配的正常流程、异常流程和 edge case。

## Impact

- 影响后端环境采集脚本生成逻辑：`SshRuntimeService`。
- 影响依赖分析事实提取和目标 provider 匹配逻辑：`DependencyFactExtractor`。
- 影响环境快照 raw summary、parse warnings、`environment_components` 写入内容。
- 影响依赖分析结果中的 `targetMatchStatus`、`riskLevel`、provider package/version 字段。
- 影响 API E2E 依赖分析模块和相关测试 fixture。
