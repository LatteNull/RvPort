## Why

现有 Scanner 已能串起简单 Make/CMake 参数、源码条件、多层宏包装和 intrinsic，但部分作用证明仍停在文件级可见性、单源 recipe 或保守的分支失效处理，不能可靠说明同一头文件在不同编译单元中究竟受哪个参数和宏定义影响。候选用途证明已经完成首版，下一步应补齐这些可静态证明的上游断点，而不是扩大关键词命中或把 unknown 直接变成已适配。

## What Changes

- 建立按目标、translation unit、configuration 和 occurrence 隔离的宏作用证明；保留构建参数、变量引用、实际使用点、include、条件、宏调用/定义/替换 token 的真实来源。
- 扩展有界 Make 参数来源：本地静态 include、已支持条件语义下的赋值分支、明确规则中的 `$<`/`$@`，以及分散在不同源码位置的 `-D` 和宏名 token；不解释任意 Make 函数或执行 recipe。
- 复用已有 CMake target usage 传播，补齐传播路径、参数冲突及作用顺序的证明，禁止拿全局源码行排序充当真实参数覆盖顺序。
- 对可见源码的对象宏别名、受限整数/布尔条件、`#if/#elif/#else` 合流、`#undef` 和固定参数宏传递提供保守求值与来源链。仅证明受支持子集，不实现完整 C/C++ 预处理器。
- 默认 V2 在同一个 Finding 的既有 evidenceChain 中展示完整来源和断点，维持上下各 20 行及命中高亮；不展示 classification/assessment 阶段节点，不改核心 schema，不要求后端另行接入。显式 V1 与 JSON/HTML/log 三工件保持兼容，新增展示说明提供中英文字段。
- 增加独立人工 oracle、逐 occurrence 正反例、隔离单元测试、完整回归及规模验收。所有新增/修改模块逐项登记，项目整体及受影响模块均须达到至少 90% 行/90% 分支覆盖率。

## Capabilities

### New Capabilities

无。本 change 扩展现有能力，不创建第二套分析管线。

### Modified Capabilities

- `kb-scanner-cpp-frontends`：补充宏调用实参与分支事件的有界、可定位记录，不泄漏原生对象。
- `kb-scanner-build-selection-analysis`：扩展 Make 参数来源和作用对象证明，建立有序、多来源的编译输入合同。
- `kb-scanner-cmake-source-analysis`：补齐 target usage 传播的来源、配置隔离和冲突处理。
- `kb-scanner-evidence-graph`：增加 TU 内宏状态、条件合流、别名/固定实参传递的有界证明与按需查询。
- `kb-scanner-report-schema-v2`：通过现有源码链结构展示新增真实端点、分支与断点，保持核心 schema 兼容。

## Impact

- 范围限定 `tools/kb-scanner`：C/C++ frontend、Make/CMake adapters、normalization、build/macro graph 与 V2 源码链，以及对应测试和文档；必要的 Detector/Classifier 接线只能消费完整证明，不重写风险策略。
- 复用现有 Tree-sitter、可选 libclang、scanner-owned Make/CMake 解析及图索引；本轮不引入必需的 LibTooling 服务、新外部工具或依赖安装，不改变 GCC/Clang 两份 x86 compiler facts 的内容、加载和追溯。
- 测试仅在独立 `kb-scanner-test` 容器执行，不安装宿主依赖、不运行项目命令、不重建生产容器；不修改其他任务目录。
- 仅做 C/C++ 静态迁移分析，不包含操作系统、交叉编译误选、真实 RISC-V 编译、测试内容语义、跨函数用途闭包或 CC-0006 有符号移位。已识别 `uname` 仍假定返回正确目标架构。
- 旧配置说明中的 V1/YAML 描述是历史背景，本轮以当前主规范及实现为准：默认 V2、显式 V1，正式知识入口不恢复 Legacy YAML。
