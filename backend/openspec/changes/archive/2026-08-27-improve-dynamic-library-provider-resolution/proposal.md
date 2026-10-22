## Why

依赖分析当前对 `libc.so.6` 这类 ELF `NEEDED` 动态库只拿到 SONAME 名称，不能稳定定位 source 环境中的实际库文件和 owner package，导致 provider 版本关系和风险判断证据不足。

同时，在默认 source 与 target 属于同一发行版包生态的前提下，如果目标环境的 SO/provides 元数据不完整，已经确认 source owner package 的依赖不应直接被判定为目标缺失；应回退到同名包和大版本匹配，避免把软件迁移问题误放大成操作系统迁移问题。

## What Changes

- 构建验证事实采集增加动态库解析观测：将 ELF `NEEDED` / `SONAME` 中的库名解析为 source 环境实际库路径，并查询该路径的 owner package/version。
- 依赖分析使用动态库解析观测补全 source owner package、source owner version、source library path 和 evidence。
- 依赖分析增加目标 provider fallback：当 target 侧通过 SO/provides 不能定位 provider，但 source owner package 已确认时，使用同发行版包生态下的同名/归一化同名 package 匹配目标已安装包或目标软件源包。
- fallback 匹配继续使用现有 provider 版本关系和风险映射，证据中明确标记 `matchedBy=source-owner-package-fallback`。
- 明确边界：本 change 不处理跨发行版包名等价关系，例如 `glibc` 与 `libc6` 的 alias 推断。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `dependency-analysis-runtime`: 补充动态库实际路径/source owner 解析，以及同发行版包生态下的 source owner package fallback 匹配要求。

## Impact

- 影响 `BUILD_VALIDATION` wrapper 的构建事实输出。
- 影响依赖分析结果提取、provider 匹配、risk/status 计算和 evidence。
- 需要补充单元测试和真实依赖分析验证，覆盖 `libc.so.6`/`ld-linux*.so*` 等典型动态库，以及目标 SO/provides 缺失但同名包存在的 fallback 场景。
