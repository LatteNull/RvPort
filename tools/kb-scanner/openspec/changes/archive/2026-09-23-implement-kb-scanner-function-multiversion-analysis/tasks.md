## 1. 固定语义边界与验收基线

- [x] 1.1 核对现有函数/属性 Evidence、归一化、图与 V1/V2 合同，记录两份 compiler facts 哈希；在独立测试容器保存修改前单元覆盖率及代表报告，不安装宿主依赖或更新生产容器。
- [x] 1.2 根据设计引用的 GCC/Clang 官方资料固定 compiler/language/source-target/mechanism 规则矩阵及版本适用范围；列出缺少 profile 时的 unknown 行为和本轮不支持构造，不执行项目或编译器探测。
- [x] 1.3 编写版本化人工 fixture/oracle，涵盖单 target、多 target/default、clone 列表、声明-only、同名重载/作用域、不同条件/配置、共享体 AVX、未知调用及不支持机制；每例明确期待事实、组状态、风险和不应出现的结论。
- [x] 1.4 建立本 change 的机器可读 unit inventory，映射所有新增/实质修改模块与 fake/mock 边界，接入包含未加载自有源码的整体及逐模块 90% 行/90% 分支门禁。

## 2. 函数身份与属性归属

- [x] 2.1 实现受支持自由函数的单次轻量 inventory 和属性 owner/body 范围，复用 byte index、原生生命周期和授权清单；补充作用域、重载、嵌套、UTF-8/CRLF、ERROR/MISSING、零预算和无属性反例的隔离单元。
- [x] 2.2 在 Tree-sitter adapter/vocabulary 中接入 scanner-owned 结构，保留原完整 attribute Evidence 值和身份；补充 parser facade 单元及真实 C/C++ grammar、属性位置、原生崩溃回归组件测试，分别统计。
- [x] 2.3 在既有 Clang 安全上下文内补充可选 canonical declaration/定义关联，规范化身份、处理冲突和不可用；补充 cindex/cursor fake 单元，覆盖跨文件、不同配置和 baseline 降级。
- [x] 2.4 实现 Normalizer 的 owner/body 引用校验、producer 合并及版本/配置隔离；补充非法引用、冲突、稳定 ID 和旧事实不变单元，在独立容器执行本节定向门禁。

## 3. 版本组和既有事实关系

- [x] 3.1 实现纯 attribute decoder 与版本化 semantic profile，区分 target 特化、多定义和 target_clones；补充混合字面量、default 精确 token、声明属性、未知 profile、非字面量/宏/foreign 和其他机制单元。
- [x] 3.2 实现 scope/signature/configuration 分桶与 default presence/definition/completeness 状态，补充条件成员、跨 TU、类型歧义、乱序/迁根、超限和输入不可变单元；禁止缺失证据被解释为 absent。
- [x] 3.3 实现函数版本非执行成员关系及精确 source/build proof 绑定，补充同文件 selected 不等于 clone selected、跨配置/悬空端点、共享体和成员边不进入执行遍历的单元。
- [x] 3.4 实现基于既有 Local Detector/事实的版本体依赖关联及专用多版本 Detector，按 span/最近 body/configuration 绑定；补充同一行多函数、嵌套体、未知调用、克隆不重复计数及候选根因合并单元，不重复建设知识词表。
- [x] 3.5 在默认组合管线接入阶段并传播失败/partial/诊断，补充 fake 驱动的顺序、上游失败短路、无属性快路径和家族分析共存单元；在独立容器执行本节模块门禁。

## 4. 分类与兼容展示

- [x] 4.1 接入 default 缺口/未决观察的 classification、risk 和 assessment 策略，补充适用规则及范围闭合、unknown/medium、原 high/blocker 保留、完整排除/inactive、无 ready/portabilityGap 升级的隔离单元。
- [x] 4.2 实现 V2 顶层 catalog 与 Finding 内自包含 function-multiversion namespace，合并已有 extension，补充 mapper/projector 的独立引用、配置、多版本预算与无假 clone 行号单元。
- [x] 4.3 接入真实属性/声明/定义证据链及明确断点，保留 ±20 行和真实命中；补充实际受影响 chain/context/validator 模块单元，验证生成版本不伪造 source step，classification/assessment 不进入链。
- [x] 4.4 实现中文/英文配对解释、标题及 suggestion 模板和中文 HTML 有界摘要；在现有 V1 合同中映射相同风险，补充 suggestions/renderer/V1 实际受影响模块的未知兜底、HTML 转义和发布失败单元。
- [x] 4.5 独立容器运行本节定向单元与 V1/V2/schema/单 Finding 离线解释/namespace 共存/共享体 occurrence 组件合同，确认核心 schema、默认版本、三个 artifact 和后端输入保持不变。

## 5. 全量质量与交付

- [x] 5.1 在独立测试容器运行 `python tests/run_source_chain_unit_tests.py --output /tmp/function-multiversion-coverage`；实际记录整体和每个受影响模块行/分支至少 90%、完整统计范围与排除理由，覆盖不足保持未完成并按需请求扩围。
- [x] 5.2 执行 `python tests/run_container_tests.py --regression-only` 及新真实 parser/CLI 组件套件，逐字段对照人工 oracle、固定 AVX/CMake/libarchive/zlib/cJSON 缩减样例和显式 V1；记录合理差异，不自动重写基线。
- [x] 5.3 提供可重复性能入口，在独立容器运行 10000/20000 轻量函数、稀疏属性组及预算压力测试，记录索引/关联计数、时间、峰值内存和完整扫描差异，调查超过设计阈值的开销。
- [x] 5.4 复核两份 compiler JSON 原字节哈希、只读输入/无项目执行、排除/根外路径、native-crash 与双语兼容；更新中文能力/边界文档和开发计划。
- [x] 5.5 编写 verification.md，列出实际命令、单元/组件/回归结果、整体及逐模块覆盖、持久报告位置、人工差异和性能；完成 OpenSpec 严格校验与相关文件格式/范围检查后交付，不自动同步归档、commit/push 或部署。
