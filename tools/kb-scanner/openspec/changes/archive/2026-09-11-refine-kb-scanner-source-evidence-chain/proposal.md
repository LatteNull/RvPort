## Why

当前 V2 evidenceChain 混入 classification/assessment 阶段，并对部分非 RPM 节点按类型排序后拼接，不能可靠表达用户需要的“命中 intrinsic ← 宏调用/定义或条件保护 ← Makefile 启用参数”。源码上下文默认前后各 2 行且最多 16 行，也不足以审阅实际代码。本 change 修正链路语义与上下文合同，并补齐代表性 Makefile 参数到源码条件宏的静态关联。

## What Changes

- evidenceChain 的代码主链仅展示有实际 Relation/ProofPath 依据的源码、宏、条件、include、目标及构建参数；从当前命中 occurrence 反查相关上游，不再按 kind 挑代表节点或伪造连接。
- 不再生成 classification/assessment step 及其连线；内部 Classifier/Assessor 继续执行，判断留在 conclusion，项目评估留在 summary。知识匹配保留自包含 provenance，作为旁支依据，不插入代码 primaryPath。
- 补齐有界 Makefile 编译参数 → 编译目标/源码配置 → 预处理条件宏 → 受保护命中关系；宏调用展开与条件宏启用分别建模，同名、相邻和单纯变量赋值不构成作用证明。
- 所有 fact、occurrence、代码 step 默认提供命中范围前后各 20 行，保留真实行列及高亮；同步调整行数/字符预算并修正截断不能优先丢弃命中的行为。
- **BREAKING（V2 详情消费语义）**：新输出不再含 classification/assessment 节点，保留 impactStepIds 字段但输出空数组；新上下文可超过旧 Schema 的 16 行/4096 字符限制。同步模型、Schema、引用规则、词汇表、示例与迁移说明，不声称旧严格 V2 validator 可无修改接受新结果。
- 保留 schemaVersion 2.0、Finding-centric 核心结构、默认 V2/显式 V1 和三个 artifact；不建立 V3、第二结果文件或 V1→V2 转换。V1 字段合同不变。
- 以人工最小跨文件 fixture、反例、逐模块隔离单测和 AVX/RPM/enum 等回归验收，记录性能与结果差异。

## Capabilities

### New Capabilities

无，扩展现有图、构建选择与 V2 报告合同。

### Modified Capabilities

- `kb-scanner-report-schema-v2`：真实源码主链、非源码依据分离、上下各 20 行、V2 合同迁移及引用/预算验收。
- `kb-scanner-evidence-graph`：命中 occurrence 驱动的有界上游子图、精确端点和多条同类宏/条件关系保留。
- `kb-scanner-build-selection-analysis`：Makefile 参数作用域、宏定义/取消及受控预处理条件的静态跨层证明。

## Impact

- 仅 tools/kb-scanner：V2 chain/index/context/mapper/model/validator/projector，必要的 build frontend/normalizer/analyzer 和源图接线，以及 schema、示例、文档、测试 inventory/runner；不修改前后端服务、其他工具目录、compose 或生产镜像。
- 不重写整个 parser、完整 Make 解释器或 C 预处理器；复用已安装解析边界，无新增运行时依赖计划。真实编译不在范围，uname 假设返回正确目标架构，不引入交叉编译误选模型；排除 ARM/OS/内核迁移。
- 原样保留 GCC/Clang 两份 compiler JSON 的字节、类别、ID 和来源；所有事实先保留，未知关联在后续阶段表达 unknown，不能当作 ready。
- 每个新增/实质修改模块必须在同一 change 映射独立 unit suite，fake 原生节点/文件读取/进程和外部边界，在独立 kb-scanner-test 容器使项目整体及每个受影响模块达到至少 90% line / 90% branch，统计纳入未被加载的自有可执行源码；组件与实扫不替代单测。具体职责映射见 design。
