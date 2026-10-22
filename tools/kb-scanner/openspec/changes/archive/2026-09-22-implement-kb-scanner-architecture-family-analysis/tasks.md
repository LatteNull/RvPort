## 1. 固定基线与人工验收样例

- [x] 1.1 核对当前扫描管线、路径安全和 V2/V1 合同，记录两份 GCC/Clang 事实哈希；在独立测试容器运行修改前单元覆盖率和代表报告基线，不安装本机依赖或重建生产容器。
- [x] 1.2 编写版本化人工 fixture/oracle：文件前后缀、镜像目录、无标记文件、单成员、foreign、不同 vendor、不同扩展名、大小写/多角色冲突、generic 内含 AVX、空文件/解析失败/排除/越界。
- [x] 1.3 建立本 change 的机器可读 unit inventory，映射全部拟新增/修改业务模块及 fake/mock 边界，接入整体和逐模块 90% 行/90% 分支门禁。

## 2. 路径观察与家族发现

- [x] 2.1 实现授权 WorkspaceSnapshot 到 scanner-owned 路径观察的传递，复用 source file ID，保存范围及解析状态；补充 inventory/frontend/normalizer 隔离单元，不为路径造代码 Evidence。
- [x] 2.2 实现版本化角色词表、词边界及局部模板提取，明确单槽位、扩展名和 unlabelled 规则；补充 paths 模块正常、边界、异常单元测试。
- [x] 2.3 实现 FamilyRecord/MemberRecord、确定性分桶及歧义保留；补充 grouping/records 的跨目录反例、乱序/迁根稳定性、单成员与 foreign 单元测试。
- [x] 2.4 实现参与路径/家族/成员具名预算、计数和截断原因；补充极值、零预算、稳定截断及输入不可变单元测试，在独立容器执行本节定向单元套件。

## 3. 图、已有证明与管线集成

- [x] 3.1 增加非执行的 architecture_family/candidate_member_of 图记录，补充 GraphStore/引用校验及候选边隔离单元测试。
- [x] 3.2 实现按 file ID/configuration 索引的现有 source/build/sibling proof 绑定；补充跨配置、歧义、悬空引用、共同编译不等于替代的隔离测试。
- [x] 3.3 在 CompositeAnalyzer 的 Detector 前接入家族分析并传播状态/诊断；补充 analyzer fake 驱动的调用顺序、失败及 partial 传播单元测试。
- [x] 3.4 审计并限定执行图查询、classification/assessment 和 proof closure，证明纯名称不增加 Finding、不改变原风险或 readiness、不撤销 blocker；补充各受影响模块单元并在独立容器验证。

## 4. 兼容报告与可见结果

- [x] 4.1 实现 V2 顶层 namespace catalog 与相关 fact.extensions 的自包含家族投影、配置 binding、候选来源和双语解释；合并其他 namespace，补充 projector/mapper 隔离单元。
- [x] 4.2 实现 catalog/Finding 双层预算、有效引用检查及裁剪原因，禁止纯路径源码行/高亮；补充 validation/context/chain 等实际受影响模块单元，验证真实源码链及 ±20 行不变。
- [x] 4.3 HTML 增加有界中文候选摘要/关联提示并安全转义，补充 renderer 单元；保持显式 V1 结构及三个 artifact，不新增必需后端输入或展示依赖。
- [x] 4.4 在独立容器运行输出定向单元和默认 V2/显式 V1/schema/单 Finding 离线解释/HTML 合同测试，确认路径-only 家族在无 Findings 时仍可见。

## 5. 回归、性能与交付

- [x] 5.1 增加 Make/CMake/Autoconf 既有选择 proof 的固定组件样例及多配置反例，逐字段对照人工 oracle；不执行被扫描项目，不用 scanner 自动改写期望结果。
- [x] 5.2 独立容器执行 `python tests/run_source_chain_unit_tests.py --output /tmp/architecture-family-coverage`；纳入全部自有可执行源码及未加载模块，整体与每个受影响模块行/分支均至少 90%，记录范围和排除理由。
- [x] 5.3 执行 `python tests/run_container_tests.py --regression-only` 及新增家族组件套件，复核现有 AVX/libarchive/CMake 等固定样例的 fact、occurrence、风险和计数差异；新增 extension 不得掩盖原结论漂移。
- [x] 5.4 执行 10000/20000 路径规模与预算压力测试，记录操作计数、时间、峰值内存和固定项目基线差异；确认没有两两枚举或新增 proof 重搜，按设计性能阈值处理超限。
- [x] 5.5 更新家族分析使用/边界文档与本地差距计划，记录已实现和仍未证明的能力；补齐 verification.md 中实际命令、测试/覆盖率、报告位置、性能和编译器事实哈希。
- [x] 5.6 执行 OpenSpec 严格验证、相关变更格式与范围检查；全部验收通过后交付并提示下一 OpenSpec 阶段，不自动同步、归档、提交、推送或部署。
