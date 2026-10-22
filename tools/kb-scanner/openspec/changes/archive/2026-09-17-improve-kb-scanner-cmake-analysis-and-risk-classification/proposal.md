## Why

demo-test1 首次扫描把已确认的 AVX/向量类型/内联汇编局部依赖统一展示为中等，把证据关系未知的 `immintrin.h` 展示为低且结论完整；同时未分析 CMake 源文件中的 x86-only 配置拒绝、目标源码与编译选项。这是“构建证据缺口”和“风险与不确定性混用”两个相互关联的问题，需要在同一 change 中贯通修正，而不是简单把全部 Finding 调成高。

## What Changes

- 新增 `CMakeLists.txt` 和项目内普通 `.cmake` 的只读、有界静态分析：恢复变量、条件、目标/源码、编译选项/定义，以及可证明的 `message(FATAL_ERROR)` 目标拒绝；复用现有统一事实、关系和 proof 管线。
- 区分 CMake 源码推导与已有 x86 构建机器产物，不把 x86 成功构建等同于 RISC-V 可选中；配置提前终止后，不伪造后续目标已经被选中的证明。
- 修正分类与投影：已确认的执行架构依赖可为高风险但未证明阻断；unknown 不再默认 low/complete；有完整排除证明的路径仍可为低风险，注释线索仍为提示。
- 保持默认 V2、显式 V1、现有字段/枚举和三个 artifact，不升级 schema、不要求后端另行接入。完善已有 reason、status、reachability 与源码证据链，以及语义一致的中文/英文建议。
- 固化 demo-test1 首次扫描源码及人工逐项预期，补齐正常、未知、互斥排除、提前终止和无副作用回归。每个新增或修改的业务模块都有隔离单元测试；项目整体与受影响模块行/分支覆盖率均至少 90%。

## Capabilities

### New Capabilities

- `kb-scanner-cmake-source-analysis`: CMake 源码安全发现、语法适配、有界求值、目标作用域与显式拒绝证明。

### Modified Capabilities

- `kb-scanner-build-selection-analysis`: 将 CMake 源码纳入正式输入，连接独立的 CMake target/source 与参数选择链，不套用 Make recipe 语义。
- `kb-scanner-classification-and-assessment`: 分离局部依赖风险、结论完整性与目标阻断，按作用范围接纳显式配置拒绝证明。
- `kb-scanner-report-schema-v2`: 在现有结构中准确投影风险/未知状态、CMake 源码上游及双语建议，禁止 unknown 默认低风险或完整。

## Impact

- 实施范围仅 `tools/kb-scanner`：build frontend/workspace、normalizer、build-selection analyzer/detector、classifier/assessment、共享风险策略、V2/V1 投影及测试/文档；若引入解析依赖，仅更新独立测试镜像依赖锁及相关构建内容。
- 优先验证可复用的维护中 CMake 语法解析器；不引入完整 CMake 解释执行环境，不在本机安装依赖。
- 两份 GCC/Clang compiler-derived JSON 内容与知识 provenance 保持不变，不退回 Legacy。
- 不执行被扫描项目的 CMake、configure、编译或测试，不涉及 OS 迁移、交叉编译误选、不更新生产容器或历史扫描记录，不修改后端/前端及其他任务文件。
- 本次只补齐明确的 CMake 静态子集和上述风险问题；完整 CMake、任意生成器表达式和预处理 `#error` 通用终止推理不在范围内，缺失证明明确保留 unknown。
