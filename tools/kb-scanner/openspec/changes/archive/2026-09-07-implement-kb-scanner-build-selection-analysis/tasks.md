## 1. 验收基线与边界合同

- [x] 1.1 建立版本化 build-selection 行为矩阵，列出 Make、generated configure/config.sub、M4、CMake File API、Meson introspection、CTest metadata、compilation database 与 RPM 的 supported/partial/unknown/deferred 边界。
- [x] 1.2 扩展 AVX 人工 baseline，为 4 个 Makefile 的 24 个 x86 flag 逐项记录文件、SourceSpan、所属变量/target、期望 selection 状态和审计说明，且禁止 scanner 自动重写。
- [x] 1.3 添加 RISC-V 专用分支、generic fallback、缺失 target path、动态表达式、循环 include、多 configuration 和冲突机器产物的人工 fixture/oracle。
- [x] 1.4 添加 Make/M4/CMake/RPM 恶意 fixture 和 marker 断言，覆盖 shell、`!=`、eval、syscmd/esyscmd、execute_process、RPM shell/Lua/include、路径逃逸和超预算输入。
- [x] 1.5 为 baseline/schema/lint 实现隔离单元测试，验证重复项、非法相对路径、越界位置、未知状态缺少 reason 以及期望计数漂移均失败。

## 2. Core 构建词汇与组合合同

- [x] 2.1 在新的正式 build vocabulary 模块定义输入 kind、architecture probe、assignment/condition/branch、source set、argument、dependency、target/package role 和 selected/inactive/not_selected/unknown 状态，不导入 Legacy DTO。
- [x] 2.2 为 build vocabulary 添加隔离单元测试，覆盖有效/无效值、稳定身份材料、metadata freeze、排序和跨 checkout 根确定性。
- [x] 2.3 实现 ProjectWorkspaceCollector，在复用既有 CppWorkspaceCollector 结果的同时安全发现受支持构建文件并保持 project-relative、exclude 和 symlink 边界。
- [x] 2.4 为 ProjectWorkspaceCollector 添加 fake 文件系统/临时 fixture 单元测试，覆盖单文件/目录、排除项、重复输入、symlink 逃逸、读取异常和确定排序。
- [x] 2.5 实现 CompositeProjectFrontend、CompositeNormalizer、CompositeAnalyzer 与 CompositeDetector 的 scanner-owned 合并器，不修改既有 C/C++ 或 Legacy 模块。
- [x] 2.6 为每个组合器添加 recording/fake 隔离单元测试，验证调用顺序、对象身份、引用完整性、Diagnostic 去重以及 complete/partial/unavailable/failed 状态传播。

## 3. Build Frontend 路由与通用安全边界

- [x] 3.1 建立 `kb_scanner/frontends/build/` 正式包和确定性 router，按路径/已验证 schema 识别 Make、Shell、M4、CMake、Meson、CTest、compilation database 与 RPM adapter。
- [x] 3.2 为 router 添加隔离单元测试，覆盖歧义文件名、未知版本、同文件误路由、不可读文件、路径逃逸和 adapter 异常逐文件降级。
- [x] 3.3 实现通用 SourceSpan/JSON pointer Evidence builder 和 parser 异常边界，确保所有 adapter 只返回 scanner-owned Entity/Evidence/StageResult。
- [x] 3.4 为通用 Evidence builder 添加纯单元测试，覆盖稳定 SHA-256、producer/configuration provenance、绝对路径拒绝、非法 subject 引用和确定排序。
- [x] 3.5 将 technology spike 中的危险构造识别迁入正式无副作用 policy 模块，并增加精确 `uname -m` token 形状白名单但不提供任何 subprocess 路径。
- [x] 3.6 为正式 safety policy 添加参数化单元测试，覆盖全部允许/拒绝形状、wrapper/管道/重定向/环境前缀、大小写/空白边界和零命令执行断言。

## 4. Make 语法恢复与受限求值

- [x] 4.1 实现正式 Make adapter，使用锁定 tree-sitter-make 恢复 assignment、condition/else、include、target/prerequisite、recipe boundary 与精确 SourceSpan。
- [x] 4.2 为 Make adapter 添加 fake parser 与真实 parser 分层测试；隔离单元 suite 覆盖初始化/parse/节点访问异常、ERROR/MISSING、超长行、重复节点和恢复 Evidence。
- [x] 4.3 实现 scanner-owned Make value domain 和不可变 environment，支持 KnownScalar、KnownList、Alternatives、Unknown(reason/evidence) 以及 simple/recursive/append/conditional assignment provenance。
- [x] 4.4 为 value domain/environment 添加纯单元测试，覆盖赋值覆盖/追加、递归引用、未定义变量、候选合并、循环、确定性和预算计数。
- [x] 4.5 实现 Make 受限 expression evaluator，支持字面文本、已知变量引用、静态分词/拼接和架构 alias 比较；将 function/call/eval/foreach/wildcard 与普通 shell 求值保持 unknown。
- [x] 4.6 为 expression evaluator 添加表驱动隔离单元测试，覆盖有效、边界、非法、嵌套引用、unknown 污染、candidate 爆炸和不执行 shell/Make 的拒绝型 fake。
- [x] 4.7 实现 Make condition evaluator，支持 ifeq/ifneq/ifdef/ifndef 与 else 链，并仅在条件完整互斥时产生 selected/inactive/not_selected 结果。
- [x] 4.8 为 condition evaluator 添加隔离单元测试，覆盖 RISC-V/x86/generic 分支、嵌套条件、未知条件、非互斥分支和缺失 endif 的 partial 状态。
- [x] 4.9 实现有限 workspace-local Make include resolver，配置 include 深度、文件数、展开步数、候选值和关系数预算，并保留循环/截断前事实。
- [x] 4.10 为 include resolver 添加 fake loader 单元测试，覆盖静态 include、optional include、变量路径、循环、symlink/绝对路径逃逸、缺失文件、预算截断和确定访问顺序。
- [x] 4.11 实现 Make target/source/directory/compile-link argument 提取器，将求值结果和 assignment/condition/target provenance 转成 build Evidence/Fact candidate。
- [x] 4.12 为 Make target 提取器添加隔离单元测试，覆盖源码列表、对象映射、target-specific variable、x86 flag、generic fallback、recipe 不求值和 AVX 代表片段。

## 5. uname 与 Autoconf 静态分析

- [x] 5.1 实现精确 `uname -m` symbolic probe evaluator，从 ScanContext 注入规范化 riscv64/riscv32，禁止调用 subprocess 并拒绝任何非精确命令形状。
- [x] 5.2 为 uname evaluator 添加纯单元测试，覆盖 Make shell/`!=`、Shell command substitution、RISC-V 分支、generic fallback、缺失路径、x86 不可达和交叉编译误选模型不存在。
- [x] 5.3 实现 generated configure/config.sub adapter，使用锁定 tree-sitter-bash 恢复 assignment、case/if、架构 pattern、branch 与 command-substitution Evidence。
- [x] 5.4 为 Shell adapter 添加 fake parser 与真实 parser 分层测试；隔离 unit 覆盖 ERROR/MISSING、未知 command、多个 case pattern、fallback、位置和逐文件降级。
- [x] 5.5 实现 scanner-owned M4 tokenizer/recognizer，仅接受批准宏调用、字面参数和架构条件，并将 syscmd/esyscmd/动态 include/未知展开标为 unsupported。
- [x] 5.6 为 M4 recognizer 添加纯单元测试，覆盖 quoting、嵌套括号、注释、RISC-V triplet、未知宏、不完整调用、可执行宏和零 Autom4te/M4 执行。

## 6. 已有机器产物读取

- [x] 6.1 实现通用 machine-metadata 边界校验与 configuration identity，规范化 workspace 内 path、JSON pointer、schema/version 和 target architecture provenance。
- [x] 6.2 为 machine-metadata core 添加隔离单元测试，覆盖未知版本、缺字段、绝对/逃逸路径、多 configuration、重复记录、冲突 target arch 和确定 identity。
- [x] 6.3 实现只读 CMake File API index/codemodel/toolchains/cache reply adapter，恢复 configuration、target、source、compile group、argument、dependency 和 artifact Evidence。
- [x] 6.4 为 CMake adapter 添加内存 JSON/fake loader 单元测试，覆盖有效多配置、缺失 reply、未知 schema、dangling reference、过期源码路径、冲突 arch 和禁止 configure/execute_process。
- [x] 6.5 实现只读 Meson introspection adapter，恢复 target、source、defined-in、compile parameter、dependency 和 artifact Evidence。
- [x] 6.6 为 Meson adapter 添加内存 JSON/fake loader 单元测试，覆盖有效/缺失/未知版本、多 target、外部 source、重复参数和禁止 meson setup。
- [x] 6.7 实现只读 CTest JSON/有界 CTestTestfile 声明 adapter，仅恢复 target/command/source 关联并将测试角色语义延后到阶段 7。
- [x] 6.8 为 CTest adapter 添加内存输入/fake loader 单元测试，覆盖有效 metadata、动态命令、未知字段、路径逃逸、缺失 target 和禁止 CTest 执行。
- [x] 6.9 实现 compilation database build bridge，复用现有 CompilationUnitContext 并在有 configuration/target provenance 时关联 source、argument 和 target，不把 entry 出现等价为 RISC-V selected。
- [x] 6.10 为 compilation database bridge 添加纯单元测试，覆盖 target arch 匹配/缺失/冲突、多个 context、x86 参数 provenance、未知 target 和不启动 compiler。

## 7. RPM 轻量正式 Frontend

- [x] 7.1 在新正式模块实现 RPM tokenizer/section parser，恢复字段、section、条件栈和项目相对 SourceSpan，不导入 Legacy parser 或 `specfile`。
- [x] 7.2 为 RPM tokenizer/parser 添加纯单元测试，覆盖 continuation、comment、重复 section、不完整 conditional、未知 directive、超长行和确定排序。
- [x] 7.3 实现 `%ifarch/%ifnarch`、`ExclusiveArch/ExcludeArch`、BuildRequires/Requires 与构建/检查 section 的受限静态求值和 provenance。
- [x] 7.4 为 RPM evaluator 添加表驱动单元测试，覆盖 RISC-V selected、x86 inactive、RISC-V excluded、generic path、unknown macro 和嵌套条件。
- [x] 7.5 实现 RPM safety boundary，将 shell expansion、Lua、动态宏/include 和未知求值传播为 unknown，不初始化 RPM 全局状态。
- [x] 7.6 为 RPM safety boundary 添加拒绝型 fake/导入审计测试，断言不导入 `rpm`、`specfile` 或 Legacy 模块，不读取 include、不执行 shell/Lua。

## 8. 构建事实归一化

- [x] 8.1 实现 BuildEvidenceNormalizer，将 assignment/probe/condition/source/argument/dependency/target/package Evidence 转成稳定 NormalizedFact 并保留全部 producer/configuration/context provenance。
- [x] 8.2 为 BuildEvidenceNormalizer 添加隔离单元测试，覆盖跨 producer 等价合并、同值不同 configuration 保留、非法 subject/Evidence 引用、unknown fact、排序和跨 checkout identity。
- [x] 8.3 实现 CompositeNormalizer 的 build kind 注册与 C++/build 合并引用验证，未知 kind 保持 partial 而不重读源码或机器产物。
- [x] 8.4 为 CompositeNormalizer build 路径添加 recording 单元测试，验证现有 C++ fact identity 不变、Diagnostic 稳定去重和 failed 引用不进入 snapshot。

## 9. Build Selection Graph Analyzer

- [x] 9.1 实现 build entity/relation builder，注册 architecture selector、variable、condition/branch、source set、directory、argument、dependency、target、package/section 与 graph endpoints。
- [x] 9.2 为 builder 添加 fake GraphStore 单元测试，覆盖稳定 ID、复用 C/C++ source Entity、平行关系、未知 endpoint/evidence 拒绝、状态 metadata 和确定排序。
- [x] 9.3 实现 BuildSelectionAnalyzer，对 Make/Autoconf/machine metadata/RPM facts 推导 selected/inactive/not_selected/unknown，并且没有 proof 时不做否定推断。
- [x] 9.4 为 analyzer 添加隔离单元测试，覆盖 RISC-V 专用、generic fallback、missing path、多 producer 冲突、partial input、非互斥条件和 build budget 传播。
- [x] 9.5 实现 selector-to-target ProofPath 物化与预算，串联 selector/configuration、condition、source/argument/dependency 和 target/package relation。
- [x] 9.6 为 build proof resolver 添加 fake graph 单元测试，覆盖完整链、平行 configuration、cycle、max depth/visited/paths、not_found 与 unknown 区分和已有路径保留。
- [x] 9.7 扩展 CompositeAnalyzer，在同一 scanner-owned GraphStore 中合并源码关系与 build relation/proof，并验证所有 Entity/Evidence/Relation 引用。
- [x] 9.8 为 CompositeAnalyzer 添加 recording/fake 隔离测试，验证 analyzer 顺序、knowledge/fact 身份、状态合并、build-source 关联和 NetworkX/Legacy 类型不泄漏。

## 10. Build Selection Detector 与 qualification

- [x] 10.1 实现 code-owned BuildSelectionDetector definition/matcher，产生 build_selected_x86_dependency、build_inactive_x86_path、missing_riscv_selection_path 和 build_selection_unknown Observation。
- [x] 10.2 为 detector definitions/matchers 添加纯单元测试，覆盖 x86 KnowledgeEntry 精确命中、inactive 上下文、缺失路径、unknown 不升级、去重和引用完整性。
- [x] 10.3 实现 CompositeDetector 合并既有 LocalX86Detector 与 BuildSelectionDetector 输出，保持 Observation 稳定身份和全部 Evidence/Knowledge/Relation provenance。
- [x] 10.4 为 CompositeDetector 添加 recording 单元测试，覆盖同一事实多来源、宏+build proof、冲突状态、failed 引用、Diagnostic 合并和不产生最终 severity/blocking/readiness。
- [x] 10.5 更新 staged qualification profile，注入 ProjectWorkspaceCollector、组合 Frontend/Normalizer/Analyzer/Detector，Classifier/Assessor/Projector 继续 recording/no-op。
- [x] 10.6 为 qualification profile 添加端到端 recording contract 测试，验证真实 build Relation/ProofPath/Observation、阶段顺序、partial/deferred 能力和零 artifact 写入。

## 11. 单元测试清单与容器门禁

- [x] 11.1 创建 `tests/build-selection-test-inventory.json`，逐个映射所有新增/实质修改业务模块、对应隔离 unit suite、fake/mock 边界和适用 component/integration 测试。
- [x] 11.2 实现 inventory 审计测试，使业务模块新增/删除/重命名、测试文件缺失、模块无 executed lines、Legacy import 或测试层级误计均失败。
- [x] 11.3 更新容器测试 runner，独立运行 build-selection unit coverage 并对目标包执行至少 90% line / 80% branch 门禁，再分别运行 frontend、knowledge/detection、graph 和 full regression。
- [x] 11.4 仅在 `Dockerfile.test`/test lock 中确认已锁定 tree-sitter-make/tree-sitter-bash 等依赖可用；不得在宿主机安装依赖、引入 `specfile` runtime、修改生产镜像或根 Compose。
- [x] 11.5 在专属 `compose.test.yml` 一次性容器中运行 build-selection unit suite、覆盖门禁、parser/component、安全、staged 和完整回归并保存可审计结果。

## 12. 验收、兼容与文档

- [x] 12.1 运行 AVX build-selection baseline，核对 4 个 Makefile 的 24 个 x86 flag 均有准确位置、变量/target provenance 和 selected/inactive/unknown 说明。
- [x] 12.2 运行 RISC-V selector 验收，确认专用分支、generic fallback、missing path 和精确 uname 语义符合规格，且不存在“RISC-V 误选 x86”结论。
- [x] 12.3 运行 CMake/Meson/CTest/compilation database/RPM component fixture，确认多 configuration、架构冲突、缺失 metadata 和不支持表达式均传播 partial/unknown。
- [x] 12.4 运行恶意 fixture 无副作用验收，确认 marker、workspace、网络/进程边界不变且没有 Make、shell、Autom4te、CMake、Meson、CTest、RPM、compiler 或项目测试执行。
- [x] 12.5 运行默认 Legacy CLI、output schema 和高价值 x86 fixture 回归，确认 schema 1.0、顶层字段、退出码、三个 artifact、YAML/`generatedSet` 与 Clang/GCC 两份事实 JSON 内容/哈希/六类计数不变。
- [x] 12.6 更新构建选择支持矩阵、技术/安全边界、AVX baseline 说明和开发计划状态，记录仍延后到阶段 7 的 test selection、Classifier、Assessor 与兼容 Projector。
- [x] 12.7 运行 `openspec validate implement-kb-scanner-build-selection-analysis --strict`，确认全部任务完成且 proposal/design/specs/tasks 与实际实现一致。
