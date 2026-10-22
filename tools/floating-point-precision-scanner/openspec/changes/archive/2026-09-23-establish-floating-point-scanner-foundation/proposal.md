## Why

现有设计已经明确了 C/C++ 浮点精度扫描器的边界与质量要求，但尚无可执行的基础框架来承载后续检测规则。先建立可复现、可验证的输入归一化与事实提取链路，可以让后续规则只依赖稳定的 canonical facts，避免把编译器、目标架构和协议差异扩散到每条规则中。

## What Changes

- 建立仅面向 C/C++ 的模块结构与最小 CLI，提供版本信息、请求校验、扫描执行和 profile 查询入口；本阶段始终不实现具体浮点风险检测规则。
- 落地版本化的请求、结果与 canonical facts JSON Schema，并遵循既有双语诊断、稳定 finding ID、确定性排序、原子输出、失败状态和退出码契约。
- 加载 `compile_commands.json` 或显式翻译单元，保留有效编译上下文，只选择 C/C++ 条目，并为被排除的非 C/C++ 条目生成可审计的双语诊断。
- 建立带版本和来源信息的 x86/RISC-V profile registry，禁止静默回退到宿主机浮点语义。
- 通过锁定的 Clang 21 前端提取并归一化浮点类型、表达式、转换、调用、源位置、宏位置和相关编译选项，生成可供后续规则消费的 canonical floating-point facts。
- 为正常、边界和异常路径同步建设单元测试与可重复覆盖率门禁；统计全部项目自有源码，项目整体和受影响模块的行覆盖率、分支覆盖率均不得低于 90%。

## Capabilities

### New Capabilities

- `scanner-runtime-foundation`: 定义扫描器包结构、最小 CLI、版本化运行时协议、确定性聚合、原子输出以及既有状态/退出码契约的运行时承载方式。
- `compilation-context-ingestion`: 定义 `compile_commands.json` 与显式翻译单元的加载、路径与参数归一化、C/C++ 选择、非 C/C++ 排除和稳定翻译单元标识。
- `floating-point-target-profiles`: 定义 x86/RISC-V 浮点目标 profile 的版本化 schema、registry、来源、校验、指纹和未知值处理。
- `canonical-floating-point-facts`: 定义由锁定 Clang 前端提取的 canonical floating-point facts、来源追踪、未知/不支持表达以及确定性序列化。

### Modified Capabilities

无。现有 `scanner-io-contract`、`scanner-failure-semantics`、`scanner-quality-gates` 与 `floating-point-risk-detection` 的需求保持不变，本变更负责实现其中属于基础框架的部分。

## Impact

- 新增扫描器 Python 包、CLI 入口、JSON Schema、内置 profile 数据、Clang 前端适配层、测试夹具和覆盖率门禁脚本。
- 开发与集成环境锁定 Python 3.11+、Clang/LLVM 21.1.8、JSON Schema Draft 2020-12、pytest 与 coverage.py；Windows 宿主机通过锁定的 Linux 容器执行 Clang 集成验证。
- 新增的协议文件会成为后续检测规则的稳定接口；schema 版本、profile 指纹和 canonical facts 版本变化必须显式演进。
- 不新增网络调用、后台服务或具体风险规则；扫描结果中的 `findings` 在本阶段为空。
