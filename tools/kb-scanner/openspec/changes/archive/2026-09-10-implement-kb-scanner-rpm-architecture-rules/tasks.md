## 1. 冻结输入合同、语义依据与测试映射

- [x] 1.1 在独立 kb-scanner-test 容器复现普通 `%if` 互斥依赖均 selected、RPM/Shell uname 漏提取、Recommends 缺失三类问题，保存分层现状与独立人工预期，不把现有错误输出当 oracle。
- [x] 1.2 核对并记录 RPM 官方宏定义/版本、global/define、可选宏和 RPM 预处理先于 Shell 的转义/注释/引号边界，锁定受限 riscv64/riscv32 profile 的可核实值及未知项；不查询宿主 RPM 或执行项目宏。
- [x] 1.3 创建 RPM 人工 fixture/oracle 矩阵，覆盖三条规则的正例、反例、unknown、子包/多条件组、可选优化、恶意输入和原始位置；记录 GCC/Clang 事实哈希及当前 V1/V2 基线。
- [x] 1.4 按 design 职责更新 build-selection 测试 inventory 和容器门禁映射，落实新增/实质修改业务文件每模块 90% line / 80% branch，fake 原生语法、源码读取、profile 和进程边界。

## 2. RPM 原始结构与 RB-0002 宏条件

- [x] 2.1 在新实现中拆出 RPM 结构恢复模块并保留 parse_rpm 入口，恢复 section/package、directive、原始 token/span 与损坏结构；为 adapter/Frontend 接线及 parser 配套隔离单测。
- [x] 2.2 实现宏值/definedness 三态、内置 profile provenance、普通/可选/条件引用与有界别名，配套 test_rpm_macros 单测覆盖未知、已知未定义、覆盖及循环/预算。
- [x] 2.3 实现受限 `%global/%define` 展开时机、顺序、分支环境和合流；补即时/延迟求值、分支同值/异值及未知覆盖的隔离单测，不支持形式明确 unknown。
- [x] 2.4 实现 `%if/%elif/%else/%endif` 与 `%ifarch/%ifnarch` 的有界条件栈、白名单表达式、三值状态、父路径与先行排除引用；配套真值表、嵌套、elif 残余和结构损坏单测。
- [x] 2.5 修正 ExclusiveArch/ExcludeArch 的宏未知和条件激活处理，分离目标许可与外层选择；配套“inactive 分支不能排除全包目标”回归及隔离单测。
- [x] 2.6 在独立容器运行本阶段 parser/macros/conditions/adapter 逐模块单测和 RB-0002 组件测试，确认互斥依赖不再无条件同时 selected。

## 3. RB-0003 内嵌 uname 与脚本选择

- [x] 3.1 实现 RPM 脚本分段与原始 spec 位置映射，复用既有 Bash parser 边界；配套 fake 节点单测覆盖 CRLF、多行、注释/引号/here-document、section/条件嵌套及解析错误。
- [x] 3.2 将精确 `%(uname -m)`、`$(uname -m)` 和反引号形式接入目标符号化，保留 probe/宏/变量引用；配套无副作用单测，包装、管道、重定向及额外命令不得被白名单接受。
- [x] 3.3 实现有界变量赋值、if/elif/else 字符串比较、case 字面 alternative 与默认分支 first-match；对未知副作用/动态展开传播 unknown，并用隔离单测覆盖状态、污染与分支互斥。
- [x] 3.4 从受支持脚本赋值恢复源码列表及编译/链接参数 occurrence 和条件来源，不推测其一定进入真实构建；补字段级单测和“只有 x86 可选优化不等于目标缺口”回归。
- [x] 3.5 在独立容器运行本阶段隔离覆盖门禁与真实 tree-sitter-bash 组件测试，校验原 spec 行列、三种 uname 形式、RISC-V/generic/unknown 路径和禁止执行合同。

## 4. RB-0004 依赖与架构宏

- [x] 4.1 实现 Requires/BuildRequires/Recommends 的有界词法、限定符、版本、多依赖和子包归属，保留逐 occurrence 源码位置；配套 test_rpm_dependencies 隔离单测。
- [x] 4.2 接入依赖中的普通/可选架构宏及求值 provenance，保留目标限定、固定架构、未知和软依赖属性；补 `%{?_isa}` 非 x86-only、包名仅候选、Recommends 和 rich dependency 降级单测。
- [x] 4.3 为 BuildRecord/Evidence 与构建 Normalizer 补齐内部引用及元数据传递，校验所有端点、逐 occurrence 身份和 unknown/inactive 事实不丢失；为所有被修改模块配套隔离单测。
- [x] 4.4 在独立容器运行依赖/Normalizer 模块覆盖门禁及 RB-0004 组件回归，确认没有 x86 字面词的未知架构宏也能保留并进入适用分析。

## 5. 完整选择图、候选判断与输出

- [x] 5.1 在 BuildSelectionAnalyzer 中建立 RPM selector → 宏/变量定义与引用 → 父/互斥条件 → section/依赖/参数 链，不能仅凭 selected 元数据生成 complete proof；配套 fake snapshot 隔离单测。
- [x] 5.2 为 RPM 条件组引入独立 identity、完备性和必需性证据门槛，取代全文件角色汇总推断；补跨组 fallback、可选优化、未知必需性及断链回归与隔离单测。
- [x] 5.3 接入显式宏/条件预算和既有构建图局部预算；补预算边界、递归、乱序输入、重复扫描和大量无关继承图的隔离单测，不放宽图额度。
- [x] 5.4 更新 BuildSelectionDetector 及必要分类策略，保证事实先保留、目标适配 occurrence 有证明才过滤、未知架构宏仍可提示，包名候选和软依赖不自动阻塞；为所有实质改动文件配套隔离单测。
- [x] 5.5 接入既有 V2 fact/occurrences/evidenceChain 与 V1 兼容投影，必要时仅添加可选 RPM extension；为被修改 projector/HTML 文件补 fake snapshot 单测，校验源码高亮、引用闭合、断点及 HTML 转义。
- [x] 5.6 在独立容器运行图/Detector/Classifier/Projector 逐模块门禁与端到端契约，检查同名不同状态 occurrence 不互相过滤、默认 V2/显式 V1 和三个 artifact 不变。

## 6. 完整验收与交付记录

- [x] 6.1 运行三条 RPM 人工 oracle 的字段级端到端对照，逐项说明现状修复后的新增/消失/分类变化，禁止自动重写人工预期以迎合输出。
- [x] 6.2 在独立容器运行所有受影响的 unit gates 与完整回归，包含现有 AVX/枚举/候选语义、非 RPM 构建输入及可用 libarchive 基线；明确区分单测覆盖与组件/全量回归结果。
- [x] 6.3 运行恶意宏/Shell/Lua/include 和超预算 fixture，校验无 marker、无项目进程、无 workspace 外读取/写入；确认两份编译器事实哈希与 provenance 不变。
- [x] 6.4 更新本地 build-selection 支持矩阵、RPM 分析与审校基线、重写开发计划，记录明确支持/unknown 子集、profile 来源、测试清单和结果；不自动更新远端飞书或生产容器。
- [x] 6.5 校验 OpenSpec 与本 change 文件范围，确认每个实质修改业务模块都有隔离单元映射且达到覆盖门槛后才标记任务完成；向用户给出下一阶段 `/opsx:sync` 与 `/opsx:archive` 命令，不擅自同步归档或提交推送。
