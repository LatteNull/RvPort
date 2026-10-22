## 1. 固定回归基线与测试向量

- [x] 1.1 将 `backend/runtime/fp-step-description-validation` 根目录最新审计作为只读 before 基线，登记 project/source/build/analysis/task 身份、BC artifact 哈希、三类诊断和 `src/vectorcalc.cpp:62` Finding；不得引用 `first-run` 或修改历史文件。
- [x] 1.2 从真实 schema 2.0 manifest/bundle 提炼脱敏的有效测试向量，并补充 schema 2.1、显式 null、未知版本、record/manifest/scope 摘要篡改和 bundle 成员损坏 fixtures。
- [x] 1.3 为 `demo-test1` 提炼本地 C++ 回归 fixtures/oracle，覆盖系统数学头、Clang 虚拟位置、项目头/宏、指针/函数指针/容器转换、真实标量转换、真实 long-double ABI 边界和归约循环。

## 2. 修复后端 BC 兼容校验

- [x] 2.1 实现受限 raw manifest 解析和 schema 2.0/2.1 字段描述，使 manifest、record、scope、artifact key 与 artifact-set identity 按各自版本的原始字段集合计算。
- [x] 2.2 保留强类型语义校验并为 2.1 严格验证 `dialect`、`standard_source`、`standard_option`；未知版本、缺失必填字段和真实 digest 篡改继续拒绝。
- [x] 2.3 增加 Java/Python canonical identity 交叉测试，证明合法 2.0/2.1 一致、2.0 不注入新增 null 字段且任何受保护字段篡改均失败。
- [x] 2.4 使用 mock 的对象存储和文件输入增加 manifest/bundle 正常、损坏、路径边界、大小、计数、引用闭包及安全清理单元测试。

## 3. 修复后端状态、分母与诊断

- [x] 3.1 定义 BC 消费结构化失败阶段和稳定双语原因码，覆盖 manifest parse/schema/identity、bundle layout、member digest、source/compile binding、materialization 和 LLVM worker。
- [x] 3.2 修改专项分析物化与降级路径，持久化安全 artifact/schema/producer 摘要和最接近根因；禁止把 manifest/bundle 校验错误统一写为 `BITCODE_WORKER_VALIDATION_FAILED`，同时保持可用 compile database 下的 AST-only 降级。
- [x] 3.3 建立共享 compile-entry 分类结果，分别统计 raw command、C/C++ candidate、唯一项目 TU、produced/failed/missing 和带稳定原因的 excluded，移除 raw/planned 取最大值逻辑。
- [x] 3.4 识别并审计 CMake/compiler probe、构建系统内部文件、重复上下文、根外条目和非 C/C++ 命令；模糊的生成源码不得仅按 build 目录静默排除。
- [x] 3.5 增加 resolver、物化、运行摘要、任务事件和 request adapter 单元测试，覆盖 READY、PARTIAL、真实 INVALID、兼容旧 manifest、项目 TU 混合 BC、AST-only、脱敏和分母一致性。

## 4. 修复 scanner 源码边界和 canonical facts

- [x] 4.1 修改位置归一化，显式识别 `<scratch space>`、`<built-in>`、`<command line>` 等虚拟来源，禁止将其相对于编译目录解析为项目文件。
- [x] 4.2 收紧项目成员继承规则，正确处理 main-file 文件省略、项目头、系统头、宏 spelling/expansion 和 `includedFrom`；无法证明归属时输出脱敏 unknown。
- [x] 4.3 实现统一 canonical scalar type 解析器，优先使用 `desugaredQualType`，保存原始类型 provenance，并区分 floating、integer、other 和 unknown。
- [x] 4.4 以数值 cast kind 和 canonical 端点共同生成 conversion facts，排除 pointer/function/member-pointer/array/record/container 等非标量转换，并保留 typedef、cv、`auto`、宏和模板场景。
- [x] 4.5 将已由子事实表达的数组下标、初始化、赋值包装等结构节点标记为 handled/transparent，将 unsupported 的 blocking 属性与具体 fact kind、规则依赖和候选绑定。
- [x] 4.6 提升 canonical facts schema、producer/mapper version 和缓存身份；增加旧缓存安全 miss、冷/热缓存等价、损坏缓存重算及绝对工作区无关测试。

## 5. 修复规则候选与直接证据

- [x] 5.1 将 mixed-precision 评估改为候选级传播：确定损失、精确/显式转换和真正缺失类型分别保留 matched、not-matched、unknown，不让无关 cast 污染整个 TU。
- [x] 5.2 将 `long-double-abi` 候选限定为项目物理文件中的 canonical type 和已证明 ABI/持久化边界，按声明身份去重并排除系统外部声明。
- [x] 5.3 为 long-double 多边界实现确定性 occurrence/分组或有界聚合，只引用边界声明与两个 profile；合法超限继续返回稳定 frontier/partial，不提高 128 上限。
- [x] 5.4 按 registry 兼容策略提升 long-double 和 mixed-precision 的规则实现版本，更新 dependency/assessment scope、稳定 ID 和 v2 contract fixtures，保持历史结果不可变。
- [x] 5.5 增加规则单元测试，覆盖真实命中、非命中、typedef/auto、精确整数常量、非标量 cast、真正类型缺失、同 TU matched+unknown、系统 long-double 洪泛、真实多边界和预算 frontier。

## 6. 同步工具规范、设计和验证资料

- [x] 6.1 更新 `tools/floating-point-precision-scanner/openspec/specs` 中 canonical facts、risk detection、shared bitcode consumption、failure semantics 和 quality gates 的主规范，使其与本 change 的版本、候选级 unknown 和直接证据语义一致。
- [x] 6.2 更新工具总体设计、shared-bitcode consumer、cache 文档和其他受影响 docs，记录 schema/rule version、虚拟位置边界、分母口径、诊断阶段和 source-preserving/build-faithful 限制。
- [x] 6.3 更新 `floating-point-precision-scanner-roadmap.md` 的实际阶段状态，并将本修复作为 P5/P6 之间的证据可信度加固项；不得宣称动态验证、AI 或其他工具工作已完成。
- [x] 6.4 更新 validation corpus oracle、verification report 模板和 benchmark 基线说明，明确本 change 不新增规则且不以隐藏 unknown 提升质量指标。

## 7. Linux Docker 单元测试与覆盖率门禁

- [x] 7.1 在 Linux Docker 中运行 backend 全部独立单元测试，外部 SSH/SFTP、对象存储、数据库、Redis、RabbitMQ 和进程连接均使用 mock；保存命令、测试数量和 JUnit 报告。
- [x] 7.2 统计 backend 全部项目自有 Java 源码以及本次受影响包的行/分支覆盖率，确保项目整体和受影响模块均至少 90%，记录 JaCoCo XML/HTML、统计范围与逐项排除理由。
- [x] 7.3 在 Linux Docker 中运行 scanner Python 与 C++ 全部独立单元/contract tests，覆盖正常、边界、异常、unknown、AST-only、缓存、预算、路径脱敏和原子输出；不得用集成测试替代单测。
- [x] 7.4 统计 scanner 全部项目自有 Python/C++ 源码以及受影响模块的行/分支覆盖率，确保整体和受影响模块均至少 90%，保存 XML/HTML 报告并证明未加载源码进入分母。
- [x] 7.5 运行完整 reviewed validation corpus，按 finding code 报告 TP、FP、FN、strict/supported-only precision/recall、exact match 和 abstention；运行固定 S/M/L 冷热缓存 benchmark 并验证语义等价和既有资源预算。
- [x] 7.6 若任一测试、整体/模块行或分支覆盖率、corpus 或 benchmark 门禁失败，保留对应任务未完成并记录差距；不得缩小统计范围、降低阈值或以无有效断言测试凑数。

## 8. 真实 API 回归与最终验证

- [x] 8.1 在隔离的 Linux Docker 测试部署中，通过真实 API 使用 project `9915a12c-9338-419e-b589-9a3984d56c62`、source revision `a019391f-89e6-4d8e-8eed-1b7871055541` 和 build run `be53c759-1e2e-459a-9f73-ef8289ecfaf2` 创建新的浮点分析。
- [x] 8.2 保存新的 task/run/result/findings/details/verification 审计，并与历史 analysis `aee4ef66-6d81-4e88-afd7-606cc7d6cc9a` 对比 BC 校验、模式、各层分母、诊断、Finding、evidence origin、稳定排序和退出码；不得修改历史审计。
- [x] 8.3 验证合法 schema 2.0 BC 被消费、三个项目 TU 分母正确、系统 long-double 和非标量 conversion 不再产生虚假 unknown；确认 reduction finding 及 build-faithful 相关 unknown 按真实证据保留或变化，不硬标 COMPLETE。
- [x] 8.4 生成中文可审计验证报告，列出全部命令、测试结果、整体/受影响模块行分支覆盖率、corpus 指标、benchmark、排除项、报告位置和前后对照结论。
- [x] 8.5 运行 `openspec validate repair-floating-point-evidence-pipeline --strict --no-interactive`，确认 backend change 与同步后的工具 specs/docs 一致，且没有 frontend 或其他分析工具改动后再完成验收。
