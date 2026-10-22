## Context

2026-09-14 按用户“V2 schema 不变，后端不另行接入”的最终约束收敛。原 build-context/target-platform manifest 和远端 producer 工作撤回，本 change 只消费现有 --input、--compile-commands、--target-arch。现有源码工作副本不等于远端 x86 构建目录，不能把不可见产物当作已输入。
现有 parse_shell 按名字标记 selected，所有 case 使用文件级组，build analyzer 会从全文件角色推断 gap；新增 Autoconf 路径必须绕开这种结论，保留其他构建前端。
configure 通常是多平台逻辑，config.guess/sub 通常为辅助脚本；生成 Makefile/config.h/config.status/cache 是特定构建结果。工具版本和 bootstrap 可能改变未来脚本，本次只证明当前字节版本。

## Goals / Non-Goals

**Goals:** 在现有输入内发现并关联配置单元，静态证明有界逻辑的接受/拒绝/unknown，保持事实、兼容报告和严格单元质量。
**Non-Goals:** 无新输入协议和后端改动，不下载/执行 configure、M4、Shell、compiler，不完整解释 Shell/M4，不做交叉误选或 OS 迁移。现有 compile database 的读取与 C/C++ 增强不改，也不将 x86 观察参数注入 Autoconf 求值环境。

## Decisions

### 1. 模块和输入边界

新增 frontends/build/autoconf 包（不可变语法记录、值/控制流、M4/单元发现）与 analyzers/autoconf_selection.py。复用锁定 tree-sitter-bash，不引入新依赖；原生节点只在 adapter 内使用，按 byte offset 计算行列，不访问 Point 或让 Node 泄漏。
BuildFrontend 对已发现的 Autoconf 文件使用一次有界读取缓存和纯配置单元分析，再转换成现有 BuildRecord/Entity/Evidence。文件必须在 workspace.files 中且 resolve 后留在 root 内；单文件 4 MiB、全部 Autoconf 内容 64 MiB、配置单元上限 256，超限明确 partial。
实现中的 256 限制按入口文件计；目录单元与入口分别保留。M4 声明上限 100000，计算 UTF-8 位置采用增量偏移，避免反复编码前缀。默认排除的 build 目录仍遵守现有参数，不自动越过排除读取。
没有辅助脚本时只产生 unavailable 事实/诊断，不运行 bootstrap；源码关联不等于观测到调用。单文件输入也允许分析，但不猜测使用者。未收集 config.status/log/cache 的执行记录，不需要敏感日志新投影。

### 2. 配置单元与关联

configure/configure.ac 所在目录形成配置单元；AUX_DIR 的字面路径和同目录/父目录 GNU 默认候选必须在输入根内。同一单元的 guess/sub 成对定位，不混用 vendor；动态 AUX_DIR 或冲突声明保持 unknown。
M4 支持无括号 canonical、注释/引号、多行字面 AUX_DIR/SUBDIRS；其他宏只作为不透明文本，不执行展开。声明仅表明需求，不能冒充生成 configure 的确定行为。
生成 configure 中的有界字面辅助调用可串联实际源码调用关系，调用参数与输出/状态只能来自本次静态求值。未绑定 config.sub 的 $1 不猜测为完整 triplet；因此独立 config.sub 常为 unknown。

### 3. 值与控制流

目标只采用已有 target_arch。精确 uname -m 绑定正确 RISC-V CPU；uname -s/-r、OS/libc、外部探测和未证明的 host/build/target 值保持未知，绝不从运行环境或 x86 编译数据库补值。
有界值支持字面、引号、简单变量/串接、批准的参数截取；不把 scanner 的架构别名归一化当作项目 config.sub 的接受规则。
控制流按真实 AST selector/first-match/嵌套处理 case（字面、*、?、字符类、|）和简单 test/if。未知条件探索有界备选路径；只有全部可达路径支持相同结论才确定，未知赋值/命令污染影响路径。默认控制流深度 64、处理节点 100000、活跃路径 128、辅助调用深度 8。循环、复杂函数、eval、动态 source、复杂重定向、未知命令等保持 unknown，不执行。
受限 echo/printf 与 exit 提供输出/状态证据。selected 不等于 accepted；exit 0 没有有效名称、打印后失败、guess 成功而 sub 拒绝不能认定规范化成功。完整配置脚本的成功仅证明分析范围，不代表真实 configure 运行。
每个可追溯事件保留路径、digest、行列、父事件、条件身份和状态；数据流引用与控制流路径连接到结论。保留 inactive 事实而不让它们进入实际终点 proof。
真实未知副作用使该路径立即停止推演；余下 raw facts 已单独保留。已在配置入口证明实际调用的辅助文件不再重复产生“假设未绑定参数”的孤立 unknown Finding，但全部辅助源码事实仍保留。
大型真实 GNU 脚本超出静态子集可以为 unknown，必须报告具体原因，不能用关键词凑接受率。

### 4. 图与报告

Autoconf metadata 单独派发到 analyzer，禁止旧 file-role gap 再次处理。事实及局部事件不删除；Analyzer 使用既有 Entity/Relation/ProofPath，结论沿源文件入口→条件/调用→输出/拒绝路径形成。
已有 missing_riscv_selection_path 表达完整拒绝；未绑定或输入不完整保持 build_selection_unknown，均限制配置/脚本版本，不能凭局部拒绝制造项目 blocker。确认配置路径拒绝也不等于 x86 指令依赖。接受保留正向 proof，不生成缺少 riscv 字面分支的问题，也不升级项目 ready。
用现有 schema 支持的 source_evidence/构建节点和现有原因字段展示，不增加枚举/字段/新结果类型来破坏封闭 schema。主链没有 classification/assessment；每节点原始代码前后各 20 行与高亮由原 source provider 提供。新增建议复用或补充成对中文/英文文案，但 JSON schema 文件保持字节不变。
读取历史源构建上下文不会改变本次 staticAnalysisOnly/compiled/linked/testsExecuted 声明。节点和稳定 ID 限定文件内容，不能证明未来重新生成的另一版。

### 5. 单元测试与验收

| 模块 | 隔离单元边界 |
| --- | --- |
| AST lowering | fake Node/Parser，真实 grammar 另列组件 |
| 值/控制流 | scanner-owned 不可变语法记录，命令不执行，正常/未知/异常/预算 |
| M4/单元发现 | 文本和已读取文件映射，父目录/动态/多单元/不完整 |
| frontend/workspace 接入 | fake reader/parser，越界/超限/缺项/无 Autoconf 兼容 |
| analyzer/build detector/classifier 必要接入 | fake snapshots，引用完整/断点/未知不升级/旧 gap 隔离 |
| 投影/建议实际修改或复用模块 | fake graph/source，默认 V2/显式 V1/±20/双语 |
| 正式可执行辅助脚本 | 对应隔离 unit，不能只靠运行成功 |

新模块登记 tests/source-chain-test-inventory.json，复用 tests/run_source_chain_unit_tests.py，纳入 kb_scanner/scripts/tools 全部自有可执行代码和未加载源码。整体及每个受影响模块行≥90%、分支≥90%；无分支明确不适用，第三方/纯数据/非部署归档/测试排除有理由，不能缩分母。
原生 parser/CLI/完整真实项目单列组件，不能抵充 unit。固定旧/新 GNU 脚本片段及真实 Autoconf 项目，记录来源/许可/hash，人工 oracle 检查 accepted/rejected/unknown 和源码 proof。AVX/RPM/枚举/候选/原生崩溃/双语/V1/V2 回归保留，修正 Autoconf 原误判的差异单列账本。
只用独立 rvport-kb-scanner-test:local 容器、只读源码/fixture、无网络、受控 /out。实际命令和覆盖 summary/JSON/HTML/日志放 .codex-tmp/autoconf-target-support-20260914，记录到 verification.md。未通过测试/覆盖不得标完成。

## Risks / Trade-offs

- [无法看到远端脚本] → 只分析已输入内容，unknown，不承诺新增采集。
- [只有 CPU 无系统三元组] → 不推测 OS/libc；实际依赖这些维度的规范化可以 unknown。
- [源码模板与未来生成版本不同] → digest 和局部证明范围，不宣称下一次构建已验证。
- [动态 GNU Shell 导致 unknown] → 固定真实 oracle 和有界终止，不扩大为项目执行。
- [旧测试固化 wildcard 接受] → 修改对应语义测试，保留其他前端与事实数据。

## Migration Plan

现有命令原样使用。缺少输入为保守降级，不依赖新后端上线；不改变 schema/知识 JSON。不自动 commit、sync/archive 或部署。测试仅独立容器。

## References

- [GNU 脚本生成与配置](https://www.gnu.org/software/autoconf/manual/autoconf-2.72/html_node/Making-configure-Scripts.html)
- [GNU 辅助目录](https://www.gnu.org/software/autoconf/manual/autoconf-2.72/html_node/Input.html)
- [GNU 规范化职责](https://www.gnu.org/software/autoconf/manual/autoconf-2.72/html_node/Canonicalizing.html)
