## Why

RVPT 对照中的 RB-0002、RB-0003、RB-0004 仍缺少正式链路支持：当前 RPM 前端忽略普通 `%if`，可把互斥依赖都标为 selected；脚本段中的 uname 分支未提取，Recommends 与依赖宏也缺少语义。需要补齐可追溯事实和有界选择分析，避免漏检、错误确定性与架构关键词误报。

## What Changes

- RB-0002：恢复 `_arch`、`_target_cpu`、`_isa`、`__isa_name` 的架构宏引用与有界条件语义，补齐 `%if/%elif/%else/%endif` 与 `%ifarch/%ifnarch` 的嵌套、互斥及 unknown 传播。
- RB-0003：识别 RPM `%(uname -m)` 及脚本段的 `$(uname -m)`、反引号形式；仅符号化精确探测，建立变量、if/case、section 与受控源码/参数/依赖的关系，不执行命令。
- RB-0004：补齐 Requires、BuildRequires、Recommends 中的宏引用、限定符、版本和子包归属；区分随目标变化的依赖、明确 x86 证据和无法判定的候选，不凭 `%{?_isa}` 或包名作阻塞判断。
- 架构相关事实始终保留；选择/过滤/unknown 由后续分析和分类承担。目标宏未知、动态脚本、损坏结构及预算截断不得静默当作 selected、inactive 或 ready。
- 补齐 selector → 宏/变量 → 条件 → section/依赖/参数 的证据链及逐 occurrence 源码位置，修复 RPM 分支分组和缺少目标路径的证明门槛，避免跨条件组借用 fallback。
- 保持当前默认 Schema V2、显式 V1 兼容和 `scan-result.json`、`scan-report.html`、`scan.log` 三个 artifact；不新增主结果结构，不涉及后端/前端服务或生产容器。
- 每个新增/实质修改业务模块必须配套隔离单元测试及 inventory 映射，独立 `kb-scanner-test` 容器中每模块至少 90% line / 80% branch，并补充人工 oracle、契约和无副作用回归。

## Capabilities

### New Capabilities

无。RPM 仍属于现有构建选择能力，不建立平行的规则或结果体系。

### Modified Capabilities

- `kb-scanner-build-selection-analysis`：扩展 RPM 架构宏、脚本 selector、依赖宏和有界条件语义；强化完整性、分组证明、原始位置及测试合同，明确精确 uname 的非执行例外。

## Impact

- 作用域仅 `tools/kb-scanner` 的新实现：`frontends/build` 的 RPM adapter/宏/条件/脚本边界、构建 Normalizer、`analyzers/build_selection.py`、`detectors/build_selection.py`，以及必要的既有分类/投影接线。计划把 RPM 语义拆到独立 scanner-owned 模块，保持 adapter 入口；不在 archived/legacy parser 或 YAML 中加规则。
- 复用现有 tree-sitter-bash 语法边界、目标架构归一化、精确 uname 符号化和统一 Fact/Relation/ProofPath；不引入完整 rpm/specfile 宏执行环境，不新增宿主依赖。Shell 解析器的现有局部记录不能被当成完整控制流证明。
- 单测覆盖 parser/宏环境/条件求值/脚本适配/依赖词法、Normalizer、图解析、Detector 及任何被修改的分类/投影模块；第三方节点、源码读取和进程边界用 fake/mock。集成与端到端测试不能替代模块覆盖率。
- 原样保留 `rulesets/riscv-porting/generated/clang-x86-entries.json` 与 `gcc-x86-entries.json` 的字节、类别和 provenance；RPM 宏配置不是新的编译器事实来源，也不启动知识采集任务。
- 仅分析 C/C++ 软件的构建/打包迁移；排除 ARM 迁移、OS/内核/驱动迁移、真实编译和仓库包可用性探测。假设 uname 返回正确目标架构，不建模交叉编译误选。
- 输入依据：2026-09-10 飞书对照文档的 RPM 补齐范围及容器 `parse_rpm` 小样例；枚举 CC-0009 已补齐，不纳入本 change 重做。
