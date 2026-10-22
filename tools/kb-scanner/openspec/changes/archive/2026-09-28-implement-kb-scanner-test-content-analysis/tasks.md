## 1. 固定基线与单元映射

- [x] 1.1 建立本 change 的手写最小 oracle 和审校清单，固定现有测试选择/源码风险/默认 V2 与显式 V1 输出、两份编译器事实 SHA-256，并记录 libarchive 822 文件已批准 manifest。
- [x] 1.2 按 design 的职责表登记实际新增/修改模块到隔离 unit inventory，保持整体自有源码（含未加载文件）及各受影响模块行/分支均至少 90% 的门禁；列明第三方/生成数据排除理由。

## 2. 原始测试内容前端

- [x] 2.1 实现 scanner-owned 测试内容记录与稳定身份，提取普通函数/main、body、直接调用、assert 参数及局部定义/写入/条件的真实 span，避免原生节点泄漏。
- [x] 2.2 在 C/C++ 前端接入需求驱动清单，保证普通测试函数不受多版本属性/枚举候选过滤遗漏；实现 partial、UTF-8、嵌套 callable 隔离和每文件/扫描总量预算。
- [x] 2.3 为记录、适配器和 normalizer 等所有实际变更模块补 fake AST/cursor/records 隔离单元测试，覆盖身份乱序、缺失上下文、损坏结构、预算、异常与旧数据缺省；独立容器运行并检查逐模块 90%/90%。
- [x] 2.4 增加真实 Tree-sitter C/C++ 和可选 Clang 组件用例，验证无 compilation database、部分解析、节点生命周期和相同位置多 producer；组件结果单独记录。

## 3. CMake 显式测试注册

- [x] 3.1 从安全忽略路径中恢复 enable_testing 与受支持 add_test(NAME ... COMMAND 本地 executable ...) 记录及其目录、条件、配置、参数来源，完成前向目标解析。
- [x] 3.2 实现同目录 DISABLED 字面属性与有序赋值，保持测试运行选择和目标编译成员独立；旧式签名、动态发现、wrapper、未知过滤/属性/配置及冲突声明保持候选或 unknown。
- [x] 3.3 为 evaluator/注册解析/相关 records 模块增加隔离单元测试，覆盖跨目录同名、前向引用、孤立片段、禁用但仍编译、未知顺序、fatal 后注册、预算和畸形输入；容器逐模块覆盖达 90%/90%。
- [x] 3.4 增加 CMake 静态解析组件反例，核查 x86 源构建 metadata 不变成 RISC-V selected、既有 Make/RPM 关系仍可使用，并以命令边界替身证明不执行被扫描项目命令。

## 4. 内容证明与现有分类集成

- [x] 4.1 建立 path/TU/configuration 的函数区间、调用、内容及 fact 位置索引，实现 TestContentAnalyzer 与管线接入，不在分析阶段读源或解析，不按测试重复扫描全图。
- [x] 4.2 实现唯一普通 main 的内容归属与同 TU 唯一直接一跳调用证明；未调用函数仅保留词法归属，重载/遮蔽/指针/跨 TU/递归/二跳/嵌套 callable 保留断点。
- [x] 4.3 实现标准 assert 适用性和宏环境关联，处理 NDEBUG、局部重定义、未知覆盖；实现同一直线 block 的单次 scalar 初始化到 assert 使用关系和 128 语句预算，不求值任意期望。
- [x] 4.4 调整测试选择与 detector 的文件共现逻辑，分离构建依赖和内容用途；核查完整性、配置及控制条件，不用单个 complete proof 掩盖必要 unknown，不删除原始 fact/Observation。
- [x] 4.5 接入既有分类/评估和根因去重，保留独立 x86 编译风险、guarded/unknown 边界及纯数据用途准入；不凭新清单设置 testInventoryComplete 或推断 generic/RISC-V 等价覆盖。
- [x] 4.6 为索引、绑定、analyzer、test asset/selection、detector、classifier/assessor 与 composite 的实际修改逐模块补隔离单元测试；覆盖三轴组合、重复 producer、配置冲突、无效引用、预算、异常和访问计数，容器门禁逐模块达 90%/90%。

## 5. 兼容报告与证据展示

- [x] 5.1 在 org.rvport.kb-scanner.test-content 可选 extension 中实现单 Finding 自包含测试语境及必要有界摘要，合并已有 namespace；不增加 V2 核心必填项/枚举或后端输入。
- [x] 5.2 投影真实注册/构建/宏条件/调用/断言链，保留各节点上下 20 行、命中高亮、配置和真实断点；不增加 classification/assessment 代码步骤，不重复计数同一问题。
- [x] 5.3 完善成对中英文标题/解释/建议、默认中文 HTML 和转义，保持 suggestion/suggestion_en、显式 V1 与三个工件及原子发布。
- [x] 5.4 为投影/展示/双语支撑实际修改模块补合成快照隔离单元测试，覆盖引用闭合、断链、多配置、裁剪、恶意文本、无相关输入与扩展共存，容器逐模块门禁达 90%/90%；另跑 schema/V1/V2/HTML/log 合同回归。

## 6. 语义审校与性能验收

- [x] 6.1 完成最小配对项目人工审校：直接 intrinsic 断言、单次绑定、唯一一跳、未调用函数、NDEBUG、DISABLED 但仍编译、完整架构隔离、未知 runtime 条件、普通数值/大小断言、codec 数据枚举、复杂框架候选、双配置冲突；区分事实、关系、分类、严重性和展示变化。
- [x] 6.2 复用独立测试容器执行既有完整回归；抽查固定 libarchive 及可用的 AVX/架构目录项目，不自动覆写历史 oracle，不保证消除历史 unknown。
- [x] 6.3 实现或扩展 1万/2万测试内容规模入口，覆盖无关 assert、稀疏架构事实和密集预算截断；支撑脚本同步隔离单元映射及 90%/90%，记录访问计数、分阶段时间、峰值资源、输入/源码哈希及报告体积。
- [x] 6.4 保持既有宏/TU 与候选用途规模回归，并在核验后的 libarchive 822 文件输入上跑两次独立进程：2 CPU/2 GiB/无额外 swap、每次 300 秒内正常发布合法三个工件；保留旧 810 文件历史及全部失败/诊断，不缩小输入或更新生产容器。
- [x] 6.5 最终运行 tests/run_source_chain_unit_tests.py 和 tests/run_container_tests.py --regression-only 对应独立容器命令，报告整体/逐模块行与分支覆盖、范围、排除、报告位置和真实执行结果；复核两份 generated facts 字节哈希不变。

## 7. 文档与阶段交付

- [x] 7.1 新增测试内容能力/边界/复跑说明，更新开发计划、extension 合同示例和人工审校记录，明确第三方框架与深层调用 deferred、有符号移位仍为低优先级。
- [x] 7.2 校验 OpenSpec strict、文档链接、差异空白和任务证据；仅在单元覆盖、回归、语义审校与性能全部完成后交付 apply，并给出同步/归档的实际下一阶段命令，不自动 commit/push 或部署。
