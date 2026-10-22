## Why

项目目前缺少针对浮点运算精度风险的统一扫描设计，无法用一致的检测边界、诊断结构和失败语义指导后续工具实现与验收。先完成可评审的设计，可以在编码前固定工具契约，并为单元测试和覆盖率门槛提供明确依据。

## What Changes

- 新增仅面向 C/C++ 源码的浮点精度扫描范围设计，定义应识别的精度损失、比较、转换、聚合误差和不稳定运算等风险类别及非目标。
- 定义稳定的扫描输入、诊断输出、退出状态与中英文展示字段协议。
- 定义无效输入、解析失败、资源限制、部分分析和内部错误的异常路径与可观察行为。
- 定义单元测试策略，覆盖正常行为、边界条件和异常路径，并要求项目自有可执行代码的行覆盖率与分支覆盖率均不低于 90%。
- 在模块根目录新增 `docs/`，写入中文总体设计文档。
- 新增中文 roadmap，定义后续独立 OpenSpec changes 的阶段依赖、交付物、准入/退出条件和质量门禁。
- 本 change 仅交付设计文档和 OpenSpec 工件，不实现扫描器、命令行程序或其他可执行代码。

## Capabilities

### New Capabilities

- `floating-point-risk-detection`: 定义 C/C++ 浮点精度风险的检测类别、适用范围、证据要求、严重性和抑制边界。
- `scanner-io-contract`: 定义扫描请求、配置、诊断结果、双语字段、退出状态及版本兼容协议。
- `scanner-failure-semantics`: 定义无效输入、解析失败、资源限制、部分结果和内部错误的处理与报告要求。
- `scanner-quality-gates`: 定义单元测试分层、测试场景、覆盖率统计范围及行/分支覆盖率至少 90% 的验收门槛。

### Modified Capabilities

无。

## Impact

- 新增 `docs/floating-point-precision-scanner-design.md` 作为模块总体设计文档。
- 新增 `docs/floating-point-precision-scanner-roadmap.md` 作为后续实施路线图。
- 新增本 change 的 proposal、design、specs 和 tasks 工件。
- 不新增或修改生产代码、构建依赖、运行时接口或部署配置。
- 后续实现 change 必须以本设计定义的契约和质量门槛为基础，不能视本 change 为实现授权。
