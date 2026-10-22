## 1. 冻结范围、输入和验收依据

- [x] 1.1 核对现有源码与本设计，建立“职责→实际文件→隔离单元 suite”清单及支持/unknown 矩阵；只改 `tools/kb-scanner`，不恢复 Legacy 或修改后端。
- [x] 1.2 固定 `44c756f` scanner 对照、容器镜像、两份 compiler facts 哈希和 libarchive 822 文件清单；创建本 change 的 verification 记录与增量差异账本，不覆盖历史审校。
- [x] 1.3 编写独立人工 oracle：Make/CMake→参数→条件→宏→intrinsic 正例，以及未使用参数、不同 target/TU/configuration、冲突覆盖、inactive、动态构造、实参未调用、循环和预算反例；预先声明预期端点/行列/状态，不从扫描输出自动生成真值。

## 2. 建立编译参数的真实作用来源

- [x] 2.1 定义编译使用实例和多来源参数的内部 records/normalization 合同，保留语义顺序依据、真实 Evidence 引用及配置；同步 DTO/normalizer 的正常、悬空引用、跨位置、顺序缺失和稳定身份隔离单测。
- [x] 2.2 扩展 Make 参数事件处理，支持静态本地 include、受支持条件赋值与 `=`/`:=`/`+=`/`?=` 展开时机；同步 fake reader/parser 的合流、未知环境、越界、环与副作用隔离单测。
- [x] 2.3 对明确单目标单源码编译命令绑定 `$@`/`$<` 和多位置 `-D/-U` token，保存实际引用点；补多 recipe 身份、错误 prerequisite、未使用赋值、pattern/target-specific/response file 等拒绝路径单测。
- [x] 2.4 完善 CMake usage 的逐 link/source/configuration provenance、等价定义合流和未知覆盖顺序/冲突处理；补 PUBLIC/PRIVATE/INTERFACE、目录、循环、外部目标和不同排序输入隔离单测。
- [x] 2.5 在独立测试容器执行本组单元与 Make/CMake 真实解析组件用例，分别核验参数原始来源、选择状态及没有项目命令执行；补齐本组模块 90% 行/90% 分支门禁。

## 3. 实现有界宏状态与参数传递

- [x] 3.1 扩展 C/C++ frontend 的实参、分支和有序事件纯数据记录，保留跨头文件调用入口和原生生命周期边界；补 fake Tree-sitter/Clang 的位置、空实参、畸形语法、producer 冲突与采集预算隔离单测。
- [x] 3.2 实现 TU/configuration 隔离的宏状态与对象别名使用时求值，区分定义为零、未定义、未知和冲突；同步受限整数/布尔表达式、晚绑定、循环、unsupported、无外部执行隔离单测。
- [x] 3.3 实现 if/elif/else 可行路径合流、define/undef、include 顺序/重入和 guard 边界；补无 else 路径、同值/冲突合流、inactive 副作用、缺失 include、不同 TU 共享头文件及预算单测。
- [x] 3.4 实现固定参数宏绑定与嵌套传递，使用调用时定义，保持实参/形参/replacement 的独立位置；补不同调用实参、实参未使用/未调用、普通函数、递归、#、##、变参和模板歧义单测。
- [x] 3.5 在独立容器执行本组隔离覆盖与真实 C/C++ parser 组件测试，确保原始 facts 保留、没有 Node/Tree/Cursor 泄漏，所有本组实际模块达 90% 行/90% 分支。

## 4. 按需生成与消费作用证明

- [x] 4.1 从现有 facts、宏调用和构建绑定建立按 TU/configuration 的作用索引及反向需求查询，覆盖尚未形成 Finding 的终端；补无需求快速路径、缓存隔离、不同输入顺序和逐调用身份单测。
- [x] 4.2 接入 Evidence Graph/build binding 和正式 Detector/Classifier 消费，终端回连原始 token fact 并复用 compiler knowledge；补 proof 引用闭合、参数被调用与仅传值区别、原事实保留及不误降 confirmed x86 风险单测。
- [x] 4.3 落实每 TU 事件/展开/新增关系预算及统计，保留既有 include 与源码链查询硬限制；补继承大图不占新增额度、截断断点、重复查询和恶意循环隔离单测。
- [x] 4.4 在独立容器验证本组覆盖及人工图链 oracle，检查 complete/inactive/unknown/conflicting 逐 occurrence 结果，确认不把作用证明当用途排除、家族等价或真实编译证明。

## 5. 保持 Finding 自包含展示与兼容

- [x] 5.1 使用既有 V2 steps/edges/occurrences 投影多来源参数和实参链，隔离 TU/configuration 并只选择真实连通 primaryPath；补 fake graph/reader 的端点、分支、折叠、缺引用、裁剪和缓存隔离单测。
- [x] 5.2 为新断点/说明提供中文及英文，维持正常上下 20 行和命中高亮、knowledge 旁支及无 classification/assessment 节点；补 HTML 转义、长行、V1 兼容、现有扩展和原子发布单测/合同测试。
- [x] 5.3 在独立容器从默认 CLI 生成 Make/CMake 正反例的 V2/V1 JSON/HTML/log，逐源码验证位置、路径、状态和双语输出；确认核心 schema 未变化且无后端新增接入需求。

## 6. 全量质量、审校和性能验收

- [x] 6.1 运行 `tests/run_source_chain_unit_tests.py --output /output/unit` 的独立容器门禁，统计全部自有生产源码（含未加载文件）和实际受影响模块 ≥90% 行/分支；新增/修改测量驱动另做隔离覆盖，记录排除项、命令及报告位置。
- [x] 6.2 运行完整回归及 AVX、固定 libarchive 822 文件、cJSON/zlib/libarchive 原生崩溃回归、CMake demo、源码链、枚举、架构家族、函数多版本、用途证明、RPM/Autoconf；对变化逐项审校，不自动覆盖 golden。
- [x] 6.3 冻结并运行 1万/2万稀疏/密集和宏/多 TU 规模样例；在 2 CPU/2 GiB/无 swap、每扫描 <300 秒且无 OOM 下记录采集、环境/索引、查询、投影/发布、工件体积和预算统计，新增功能相对成本仅作诊断。
- [x] 6.4 更新本 change 验证记录、模块测试映射、构建支持矩阵和开发计划，明确首版能力与 deferred；核对 compiler facts 原字节、V2/V1 合同、不执行项目及不安装宿主依赖边界，运行 OpenSpec strict 校验。所有验证完成后再提示用户同步归档，不在本任务自动 commit/push 或部署。
