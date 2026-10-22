## Why

当前 Scanner 能通过已连接的构建/条件证据判断实现选择，但不能独立归纳尚未连接构建元数据的 `foo_x86.cpp`、`foo_generic.cpp`、`arch/riscv/foo.cpp` 等实现家族。这使报告难以回答“这个 x86 实现附近是否还有通用或 RISC-V 候选实现”，也不能清晰区分没找到候选与已经证明缺少替代实现。

## What Changes

- 基于已授权、已收集的 C/C++ 文件清单，增加确定性、受预算约束的架构家族候选分析，支持同目录文件名变体和镜像架构目录。
- 区分路径观察、候选成员、已有证据支持的选择/替代关系；名称不证明指令集依赖、功能等价、目标选中或通用实现可用。
- 将家族成员与已有 source Entity、构建配置和证明关联；候选边不参与执行依赖遍历，不以候选存在撤销 blocker，也不以候选缺失增加 portability gap。
- 默认 V2 通过现有 namespaced extensions 输出有界家族目录，并在相关 Finding 中嵌入所需候选信息；有真实来源的证明继续使用既有源码链、命中上下各 20 行及双语建议。纯路径不伪造行号，不新增独立报告。
- 保持显式 V1 的既有结构、默认 V2 schema 2.0 及 JSON/HTML/log 三个 artifact；无需后端改造或新参数。更新使用说明和差距记录，明确这是候选归纳而非通用等价证明。
- 为每个新增/实质修改业务模块配套隔离单元测试、完整源码行/分支覆盖率门禁和字段级回归。

## Capabilities

### New Capabilities

- `kb-scanner-architecture-family-analysis`：路径家族发现、作用域隔离、候选角色与歧义、证明关联、安全与资源边界。

### Modified Capabilities

- `kb-scanner-evidence-graph`：新增非执行语义的家族成员关系，并隔离候选边与已证明 alternative 关系。
- `kb-scanner-classification-and-assessment`：规定家族候选对风险、替代完整性和项目评估的保守影响。
- `kb-scanner-report-schema-v2`：在既有 extension 合同中展示家族候选、来源和完整性，不改变核心 schema 或伪造代码节点。

## Impact

影响范围为 `tools/kb-scanner` 的 scanner-owned 模型/分析器、默认组合管线、相关分类与投影、测试和文档。优先使用 Python 标准库和已有 WorkspaceSnapshot/Evidence Graph，不引入新解析器或运行依赖；不重新递归扫描磁盘，不执行项目脚本。

两份 GCC/Clang 编译器事实 JSON 保持原字节和加载合同，路径角色提示与编译器事实分离。当前实现以已同步的默认 V2、显式 V1 主规范为准，不恢复历史 YAML/Legacy 路径。

不包含函数多版本 default 完整性、通用跨函数值流、复杂宏展开、intrinsic/汇编等价替换、独立汇编、操作系统或内存模型迁移；不建模 `uname` 交叉编译误选，不执行真实编译/测试，不修改后端、生产容器或其他任务文件。

单元测试映射涵盖路径归一/角色识别、家族分桶/预算、图与证明绑定、管线集成、分类影响和 V1/V2 投影；外部 filesystem/parser/graph 边界使用 fake/mock。仅在独立 `kb-scanner-test` 容器安装依赖及执行测试；全部自有可执行源码（含未加载模块）与每个受影响模块均须行覆盖率和分支覆盖率至少 90%，高层回归不替代此门禁。
