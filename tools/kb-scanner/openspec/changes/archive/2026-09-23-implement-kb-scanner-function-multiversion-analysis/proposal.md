## Why

架构家族分析已能发现文件级候选，但目前 attribute Evidence 尚未可靠绑定到函数声明、定义及版本组，无法解释同一函数是否有 default/fallback、这些版本共用还是分别拥有函数体，以及已有 x86 事实属于哪个版本。需要补齐这一层静态语义，避免把出现 `default` 当作 RISC-V 可用，或把单个 `target("avx2")` 函数误判为缺少多版本 fallback。

## What Changes

- 为有真实多版本属性的函数建立有界声明/定义身份、属性归属和函数体范围，复用 Tree-sitter 基线与可选 Clang 语义增强，保留原始 Evidence 和编译配置。
- 首版分析 GNU/标准属性拼写的 `target` 与 `target_clones`：区分单个 target 特化、多定义版本组、一个函数体的 clone 列表；非字面量、宏包装、跨 TU 歧义及其他机制明确 unknown。
- 独立表达版本组完整性、显式 default 的声明/实现状态、局部 x86 依赖、已有目标选择证明和工具链适用性。default 仅是该机制的基线版本，不自动等价于通用源码或 RISC-V fallback。
- 保留全部扫描事实；仅在有范围限定的完整证据和适用语义规则时报告 default 缺口。已确认 x86 依赖继续使用既有风险策略，不能因为另一版本存在而撤销 blocker；缺少证据保持 unknown，供后续机制补齐。
- 默认 V2 以既有 `extensions` 自包含展示函数版本组及真实源码链，保留上下各 20 行和双语建议；显式 V1、核心 schema 2.0 和三个 artifact 保持，不要求后端改造。
- 配套隔离单元、正常/边界/异常反例、字段级人工 oracle、性能与整体/逐模块 90% 行及分支覆盖门禁。

## Capabilities

### New Capabilities

- `kb-scanner-function-multiversion-analysis`：有界函数版本组、default 存在与定义状态、版本体依赖关联、工具链适用性和资源边界。

### Modified Capabilities

- `kb-scanner-cpp-frontends`：函数身份、属性归属与声明/定义范围的可定位 Evidence，保持原生对象生命周期和字节位置安全。
- `kb-scanner-evidence-graph`：版本成员与真实函数体依赖关联，隔离源码共存、执行可达和替代证明。
- `kb-scanner-classification-and-assessment`：default 缺口及不确定性分类，保持既有 x86 风险与范围限定。
- `kb-scanner-report-schema-v2`：通过既有 namespace extension 展示版本和 fallback 信息，保留自包含源码链与输出兼容。

## Impact

仅涉及 `tools/kb-scanner` 的 C/C++ 前端/归一化、专用分析器和 Detector、组合管线、分类/评估及 V1/V2 投影、测试和文档。优先复用现有 Tree-sitter、libclang、scanner-owned 图和标准库，不新增运行依赖、不恢复 Legacy/YAML。当前合同以已同步的默认 V2/显式 V1 主规范为准。

两份 GCC/Clang generated JSON 原字节、加载及 provenance 保持；工具链多版本语义以带官方来源的版本化 code-owned 策略表达，不能冒充新编译器事实。现有 x86 构建输入仅提供源侧上下文，不能证明目标工具链接受这些属性。

不实现任意手写 dispatcher、IFUNC resolver、函数指针值流、运行时 CPU 特性求值、函数等价证明或全程序调用图；不扩大 ARM/操作系统/内存模型迁移，不建模 uname 交叉编译误选，不执行项目、编译或测试命令。所有新增/修改模块须有 fake/mock 隔离单元映射；全部自有源码含未加载模块和各受影响模块须分别达到 90% 行/90% 分支。验证仅在独立 scanner 测试容器进行，不安装宿主依赖、不修改生产容器或其他任务。
