## Context

项目当前只有 `doc/`、编译探针和三个文档规范；本 change 交付第一个可执行基础设施切片，不交付完整内存序分析器。需求方已明确生产输入是 GCC/Clang 的用户态 C/C++，开发 Dockerfile 在本 change 创建、构建和验证，与生产 Dockerfile 的合并另立 change。

### 已有证据与设计约束

| 实测事实 | 对本设计的约束 |
|---|---|
| 2026-09-10 Clang 18.1.3：27 BC、74 项表达检查 | 固定为历史编译证据，不等同于检测准确率 |
| 2026-09-11 DevKit 25.3.0 / 自带 LLVM 16.0.4 接受单 TU compile-only BC | 自有流水线不需要生成或运行最终可执行程序 |
| bc-gen 退出 0，但零产物；补齐 GCC 头路径后才产生 BC | 校验隐式编译环境、产物数量、警告和 reader 结果 |
| 三个独立 TU 的 object BC 扫描建议数为 0；链接后为 2/3/4 | 目标范围和跨模块索引必须显式建立，目录不代表程序 |
| 缺 debug 后零建议；正确 release/acquire 仍被建议加屏障 | 映射缺失必须降级，屏障建议不能当作并发正确性证明 |
| 一份上游 LLVM 18 BC 被 DevKit reader 接受 | 只记录样本兼容，不保证跨版本通用兼容 |

本轮历史实验入口为 `D:/projects/RvPort/.codex-tmp/mmcheck-20260911-4r5di2/RESULTS.md` 及同目录原始包，包 SHA-256 为 `aad9efcf2493493eb2b79b73fb93fd647aa23d726ba49e27c2ecca5d31dec9f1`；322 个文件哈希已核验，47 份 JSON 声明扫描成功。临时记录中“容器以后创建”的措辞是已被用户纠正的历史理解，不是本 change 范围。

## Goals / Non-Goals

**Goals:**

- 从全新开发镜像中复现：工具链检查 → 配置级 TU → BC → 结构化事实 → 有限范围关联 → 完整性报告。
- 验收 GCC/Clang C11/C17、C++17/C++20 输入，保留原始与分析配置、来源证据和不支持项。
- 使一个多物理文件的小工程具备可追溯的直接调用/全局引用关联，而不冒充线程或别名分析。
- 当前 change 提供单元测试、项目整体及模块级 >=90% 行/分支覆盖率门槛、独立开发 Dockerfile 的实际构建验证。

**Non-Goals:**

- MSVC/clang-cl、内核/MMIO、OpenMP/CUDA、完整 C++ modules/PCH/unity 适配、厂商扩展语义等价性保证。
- 全程序 points-to、虚调用穷尽解析、函数效果摘要传播、线程/MHP/HB/rf 分析、风险分类、自动修复或机器码等价证明。
- 自动执行任意构建命令、获取完整原生链接图、解析归档成员选择或动态符号覆盖；CMake File API 自动导入留给后续。
- 接入 SVF/PhASAR/GenMC/herdtools7/DevKit 运行时，修改远端环境或把 SSH 作为 CI 前提。
- 合并开发/生产 Dockerfile、修改仓库根 CI/容器及旧 checker。

## Decisions

### D1. C++ 事实核心与 Python 编排分离

使用 C++20、LLVM BitcodeReader/IRReader、Verifier 和 IR API 读取真实 Module；Python 负责输入校验、命令适配、进程生命周期、缓存清单和报告组织。CMake/Ninja 构建 C++，GoogleTest 测试核心，pytest 测试 Python。跨进程使用带 `schema_version` 的 JSON 文件；诊断写 stderr，机器输出不夹杂日志。首版不把全部 LLVM 图序列化到 Python，只导出需要的实体与边。

建议实现布局：`src/` 为事实读取/索引库及 worker，`python/memory_order_analyzer/` 为编排包，`schemas/` 为契约，`tests/unit/` 与 `tests/integration/` 分离。提供 `python -m memory_order_analyzer` 入口，子命令为 `doctor`、`collect`、`import-bc`、`index`、`link`；C++ worker 是内部工具而不是第二套公共 CLI。

替代方案：纯 Python 正则读取 `.ll` 无法可靠承载 LLVM 语义；立即引入所有分析框架增加版本、许可和调试成本。本阶段两者均不采用。

### D2. 当前交付独立开发容器

在项目根创建 `Dockerfile.dev`、项目级 `.dockerignore`、`config/toolchain.lock.json` 和开发/测试说明；构建上下文为本项目，不 COPY 仓库根或兄弟项目。以 Linux amd64 为必验主机平台，ARM64 容器移植不作为本 change 完成条件；AArch64/RISC-V header-free BC 生成可作目标编译冒烟，不能据此声称支持完整跨编译 SDK。

首选 LLVM 21 系列作为工具链验证候选，不在提案阶段虚构已构建的补丁版本。实施第一步必须锁定可获取的具体版本、镜像 digest、依赖来源/校验值及许可证清单；Clang、LLVM 开发库、opt、llvm-link、llvm-cov、llvm-profdata 使用同一锁定发行。若候选无法构建，在扩展实现前记录诊断并更新设计和锁文件，不静默换版本。DevKit 16 与历史探针 18 不决定生产 reader 版本。

镜像包含 GCC/G++、Clang/LLVM SDK、Python、CMake/Ninja、GoogleTest/pytest 和覆盖率工具；不包含 DevKit 或 SSH 凭据。下载仅发生在显式构建/依赖获取阶段，版本锁定；运行质量检查不联网。默认非 root 运行、源码只读挂载、构建/缓存/报告放单独可写挂载，Linux 支持匹配 UID/GID，写回文件不要求特权容器或 Docker socket。

拟交付命令（此处是实施后接口，不是已经执行）：在项目目录 `docker build -f Dockerfile.dev -t memory-order-analyzer-dev:foundation .`；提供项目脚本运行隔离构建和验收。完成条件包含从干净镜像构建项目、实际跑测试/覆盖率和 collect/index smoke，记录镜像 ID 与命令。与生产 Dockerfile 的合并不在任务清单中。

### D3. 有效编译上下文是第一等数据

`BuildSnapshot` 保存运行配置和来源；`TUManifest` 保存原始记录、实际解析 argv、cwd、源文件、生产编译器身份、分析编译器身份、语言/标准、target/ABI/CPU、sysroot、SDK 身份、相关环境白名单、响应文件内容和参数适配日志。`arguments` 必须是字符串数组且优先使用；`command` 只支持明确的 POSIX argv 编码，不经 shell 执行，遇到管道、重定向、变量替换/命令替换等执行语义则拒绝。驱动默认限定 gcc/g++/clang/clang++ 及已配置的交叉驱动；已知 ccache/sccache wrapper 可剥离并记录，未知 wrapper/插件注入按不支持处理。

宏与搜索路径是有序序列，不能用字典合并 `-D/-U`。响应文件按编译器语法展开，相对路径按已验证的驱动工作目录语义处理，限制递归与大小并诊断循环。缺参数时记录 driver 有效默认语言/标准，不擅自改成项目示例标准。MSVC/clang-cl、GPU/PCH/module 标记及无法证明安全转换的参数报明确 unsupported，不静默删除。

生产编译器探测在受限 runner 中执行，记录版本、搜索路径/宏摘要等有语义作用的环境；不输出任意宿主环境或敏感变量。分析 Clang 使用显式 GCC 安装路径/sysroot 等可解释适配，不批量伪造 `__GNUC__` 等宏来宣称等价。将参数划分为保留、转换、移除（仅原对象/依赖输出等与分析无关项）、不支持，逐项留痕。生成源码/头文件必须预先存在；不自动运行数据库内的生成器。

`CompileContextId` 基于 canonical source、cwd、有效有序语义参数和工具链/SDK 身份，不包含数据库条目序号，外部路径不缩为 basename。完全相同的重复记录可映射到同一 TU，但保留全部原始记录引用；不同宏/目标/语言/配置必须保留。`ArtifactKey` 再包含实际源/头/响应文件内容指纹、分析 profile 和 schema/工具版本。目标成员关系由另一个 `ScopeId` 表示，不能混入 TU 身份造成不必要重新编译。

缓存前每次重跑同配置依赖发现（含系统头依赖），不仅校验上次列出的头文件：新文件可能遮蔽旧 include 或改变 `__has_include` 分支。记录新依赖集合和内容，SDK 无稳定身份时禁止缓存复用。编译后确认输入未在采集与编译间变化，不一致重试一次后报 `inputs_changed`，不发布结果。

### D4. BC pipeline 与事实契约

`collect` 以 source-preserving profile 起步：使用已适配上下文生成 `-O0 -g -emit-llvm -c`，明确移除/替代原优化和 LTO 输出参数，不承诺 O0 完整保留源语义。可另选 build-faithful profile 保留原优化等级，两类结果拥有不同 artifact 身份，不能混合事件。DevKit 专有 `-fno-opt` 不进入上游 Clang 默认参数。

调用 Clang 的依赖输出能力采集实际 include 信息；首版不实现完整 AST 索引、宏展开图或库包装归一化。C++ O0 内的 atomic 包装表现为调用及其函数体中的 IR 事件，保留 CFG 和调用信息，不把包装形参的所有分支当成调用点确定事件，也不为默认 seq_cst 猜固定整数。未做过程间特化必须在 capabilities 中声明。

产物写入独立临时位置，只有退出成功、预期文件存在且非空、BC parse 和 LLVM verify 成功后才发布；退出 0 但无产物为 `artifact_missing`。限制进程时间和日志大小，超时终止所启动进程组，失败记录保留但不入成功缓存；绝不执行被分析程序或 native link。

`import-bc` 接收 BC 加来源 manifest；缺来源也能读取 IR，但 producer/config/source 身份未知，禁止宣称构建完整或进入明确配置的联合分析。文件扩展名和 magic 仅作初筛，reader/verify 给出独立诊断；先严格校验来源中的 target/layout 与 BC 是否一致，不能修改 triple 假装重新编译。厂商/跨版本模块必须实际通过 reader 和 verifier；成功不升级为全版本兼容声明。

最小 `ModuleFacts` 包含：模块 hash/target/layout、函数和全局的定义/声明/linkage、基本块和 CFG 边、直接/间接调用、内存事件、debug 原始位置及 inline 链。事件覆盖普通/volatile/atomic load-store、atomicrmw、cmpxchg（成功/失败序、weak）、fence（order/syncscope）、内存 intrinsic；未知 intrinsic/inline asm 保留 opaque effect，不当作零影响。地址只恢复可确定的 global/alloca/参数及常量 GEP；其他地址为 unknown，首版不做指针 points-to。

事件键基于 artifact/module、链接符号、基本块/指令位置，不依赖显示变量名或源码行号；只保证同一模块内容与同一 extractor 版本的稳定性，BC 重生成后不承诺指令号持久。保留不带 debug 的 IR 事件，源码 hash 不符、debug 缺失或系统头不可映射只降低映射状态，不删除事件或猜行号。

### D5. 受限跨 TU 关联而非全程序推理

`scope.json` 是本阶段显式输入，记录目标 ID、成员 ArtifactKey、来源（例如用户确认的构建目标）、成员列表是否封闭、外部边界、版本。没有 scope 时仅做分模块事实输出/候选查询，scope 状态为 unknown；不能根据共同头文件、output 路径或 BC 目录推断目标。这个文件不是 compile_commands.json 的替代品，后者继续负责 TU 配置。

索引按 `(ScopeId, linkage symbol)` 解析外部引用，内部符号按 `(ArtifactKey, symbol)` 隔离。仅对范围内唯一、兼容、无覆盖歧义的强定义绑定直接调用及明确全局引用；全局 extern 声明不新建存储。重载使用实际 mangled symbol。函数指针/虚调用保留 indirect/unknown；weak/COMDAT、别名/ifunc、动态库覆盖、归档成员选择等不支持唯一解析的情况保留候选/原因，不能随便选一个。声明可记录 known-external 类别，但未建模效果仍未知。

检查相同 triple/layout 及构建变体兼容性，禁止同一源码的互斥配置混在目标中；不同 TU 的不同编译选项不一概视为不兼容，而由显式目标成员证据及关键 ABI 配置判断。重复强定义拒绝链接。显式 `link` 仅接受已选范围，登记输入 lineage 并对结果再次 verify；默认多模块索引不要求 linked BC。禁止把 linked BC 与已包含的 object BC 重复计入同一语义范围；导入无 lineage 的 linked BC 不猜它的组成。

本 change 不传播函数内存效果摘要：`A -> B` 只表示调用绑定，不宣称 A 必然写了 B 的对象，更不宣称并发。后续 points-to/summary/thread 后端只通过 facts/index/schema 接口接入，保留 unknown 和 evidence 字段；不提前承诺 SVF/GenMC 能接受当前所有产物。

### D6. 完整性报告是产品契约

`RunReport` 版本化并引用 manifest/facts/index，记录输入记录数、唯一计划 TU 数、BC 生成/读取/校验数、缓存命中、失败分类、scope 来源、直接调用解析数、未知/候选数、可映射事件比例和 warnings。基于整个计划集统计，失败 TU 不能从分母消失。分母为零时比例为 null，不是 100%。

分别输出：`build_status=complete|partial|failed|not_applicable`、`ir_status=complete|partial|failed`、`source_mapping=complete|partial|unavailable`、`scope_status=declared|partial|unknown`；每阶段还有 `completed|failed|timed_out|unsupported|not_run` 执行状态。这里 complete 仅指该基础设施阶段的已声明范围，不代表全部外部函数/同步已分析。始终写 `semantic_analysis=not_run`、`safety=not_evaluated`、`findings=null`，而不是空 finding 数组伪装为已经扫描无缺陷。

退出约定：0=请求的基础设施操作完成且无该操作完整性缺口；2=保留了可用部分产物但存在输入/映射/范围/执行缺口；1=请求非法、全失败或不可继续的运行错误。不存在风险退出码，因为本阶段未做风险判定。`collect` 未请求 scope 时不因没有 scope 一律失败，但报告仍显示 unknown；`index/link` 缺少必要范围必须显式失败或降级。返回非零时仍尽力发布结构合法的失败报告。

### D7. ARM 证据转为离线回归，不依赖在线服务

实施时将本轮临时材料中必要的环境、源 hash、命令、代表报告和矩阵保存到 `doc/experiments/results/devkit-25.3.0-20260911/`，原始导入文件保持字节/哈希不变；需要路径脱敏的副本明确标记派生文件并保留映射，不把无关系统日志或整套 DevKit 二进制复制进项目。manifest 保留总数/原始包 hash 与实际纳入的子集，不能声称整个 322 文件包已提交。

更新 `DEVKIT_BC_VALIDATION.md`、`BC_PIPELINE.md`、`CROSS_TRANSLATION_UNIT_ANALYSIS.md`、构建适配文档及 README，保留 2026-09-10 阻塞历史，并新增 2026-09-11 实测章节。`openspec/config.yaml` 在实施时更新当前阶段/实测背景，归档 change 不改写。文档不把 PART 宏划分 TU 夸大成三个物理文件工程；新的集成测试再提供真正三个物理文件对照。

第三方屏障建议不作为自研规则的 expected-positive 真值。本阶段用它们检验证据读取、状态解释和已知局限；未来风险规则另配有明确语义预期的测试。

### D8. 测试与验收门槛

单元测试覆盖 C++ reader/事件/index/JSON、Python context/runner/cache/report、质量门槛脚本，以及现有 `doc/experiments/probe_bc.py` 的自有可执行逻辑。可为可测性作范围内重构，保持历史证据不变；固定 IR 正则探针不进入生产读取器。测试正常、异常、边界、未知和确定性；所有新/复用代码的任务与测试同步完成。

C++ 使用 GoogleTest 与 Clang source-based coverage，Python 使用 pytest + coverage.py（branch enabled）。仅单元测试产生用于 >=90% 门槛的 profile，集成/容器 smoke 的覆盖数据分开，不补高单元覆盖率。枚举全部自有执行源码，包括未 import 的 Python 和未触达的 C++ 翻译单元；全项目合并命中行/分支的计数，且每个语言及受影响模块分别达标，不能平均百分比遮蔽低覆盖模块。支持的行/分支均至少 90%；不支持指标注明原因且不能用来规避可用分支工具。

明确排除仅第三方代码、生成代码、测试框架与纯被测输入夹具；项目自有工具/启动脚本/探针不可因难测而排除。输出统计范围、排除理由、命令、失败测试、HTML/JSON 报告位置，覆盖率不足使质量入口非零退出。门槛脚本自身用合成覆盖数据测试 89.99/90、分支不足、缺失文件/报告等边界。

集成矩阵包括：GCC/Clang 编译数据库、四种语言标准、多物理 TU 直接调用/extern、同名 static、重载、宏变体、重复定义、缺头文件、零退出无产物、无 debug/源码不匹配、无效/不兼容 BC、未知调用、超时、缓存依赖遮蔽、object/linked lineage；只编译/读 IR，不运行竞争程序。镜像中从干净输出目录执行项目构建、单元测试、覆盖率和集成测试；历史 74 表达检查与 47 mm-check 报告不算单元测试达标。

## Risks / Trade-offs

- [LLVM SDK/镜像依赖不能完全离线获取] → 固定来源和版本并保存镜像身份；构建失败保留未完成任务，不退回兄弟镜像冒充独立构建。
- [GCC 隐式环境与 Clang 不一致] → 显式探测和适配日志，扩展不支持则拒绝；BC 成功不宣称生产语义等价。
- [O0 包装分支使事实多于实际调用路径] → 输出原始 CFG/调用与阶段限制，不做无根据的常量特化或同步判断。
- [只有局部范围和直接符号解析导致能力有限] → 限定首阶段结果是事实和关联，不设置误导性风险计数；复杂行为保留 unknown。
- [缓存误命中] → 重新依赖发现、内容指纹、SDK 锁定、编译前后输入一致性检查；不确定时重编译。
- [并发写产物或超时留下残片] → 每任务独立临时目录、成功后原子发布、进程组超时控制与受限清理路径。
- [历史脚本单元测试不足] → 将其纳入本项目覆盖清单与本 change 任务，不动无关兄弟代码、不降低门槛。
- [临时 ARM 证据未来不可用] → 首批任务先提取可移植子集；若原包丢失或 hash 不匹配，报告缺口，不伪造补齐。

## Migration Plan

1. 固化 ARM 证据和支持范围，锁定/验证工具链，创建并构建独立开发镜像。
2. 实现 schema、基础库和单元测试；完成 context、BC、index、report 的纵向集成。
3. 运行完整单元覆盖率和容器内离线集成验证；补齐文档与命令。
4. 全部质量门槛通过后才标记实施完成，提示后续 sync/archive；本次 propose 不执行实现或归档。

新功能只增加本项目文件，不接管旧 checker。失败时保留诊断和独立产物，不修改用户源码；需要撤销部署时停止使用新 CLI/镜像即可，不需要恢复生产容器或远端配置。开发/生产 Dockerfile 合并另立 change。

## Open Questions

- LLVM 21 的具体发行/补丁、基础镜像 digest 和依赖锁定值需在实施起始兼容性任务实测确定；未确定前不发布“可复现环境已完成”。
- 首个真实业务工程的 target/scope 元数据样例尚未提供，本阶段以显式 scope manifest 和集成夹具验收，不虚构完整原生链接拓扑。
- SVF 许可适配、外部模型检查器版本及完整线程/库摘要均为后续选型问题，不阻塞本基础设施切片。
