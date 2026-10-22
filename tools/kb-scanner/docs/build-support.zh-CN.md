# KB Scanner 构建选择支持矩阵

[English](build-support.md) | 简体中文

本矩阵记录当前构建输入的静态分析边界。所有输入只读；扫描器不执行项目命令。

| 输入 | supported | partial / unknown | deferred |
|---|---|---|---|
| GNU Make | 字面/变量赋值、已知引用、条件、静态 include、源码/参数/依赖/target | 动态 function/include、循环、预算截断、普通 shell | 完整 Make 语义、recipe 执行 |
| configure / config.guess / config.sub | scanner-owned AST、有界变量/参数截取、case first-match、简单 if/test、正确 `uname -m`、受限输出/exit、字面辅助调用与跨文件证据 | 未知 OS/libc/参数、外部命令、复杂 Shell、路径/语法/图预算；局部未绑定拒绝不升级项目 blocker | 执行脚本、重新生成或下载辅助文件 |
| configure.ac / M4 | 无括号 canonical、多行字面 AUX_DIR/SUBDIRS、配置单元/同目录辅助文件对；保留既有 M4 原始事实 | 声明不等于已执行；缺失辅助文件、动态目录/宏展开、syscmd/esyscmd/include | Autom4te/M4 求值、追踪未来生成版本 |
| CMake | 既有 File API JSON；CMakeLists.txt/普通 .cmake 的有界命令、条件、target/source/link usage 与参数 provenance | 动态表达式、未知 schema、悬空引用、冲突配置及无依据的定义覆盖顺序 | 运行 configure、完整 CMake DSL |
| Meson | 已存在 introspection JSON | 缺失架构、未知版本/字段、冲突配置 | `meson setup`、解释 Meson DSL |
| CTest | 已存在 JSON、显式 test role/target/source/argument/dependency 和静态选择关系 | 动态 command、缺失 target/source、仅命名候选 | 测试执行与通过状态 |
| compilation database | 既有 context 的 source/argument 与明确 target provenance | 缺少 target、多个冲突 context | 启动 compiler 或生成 database |
| RPM spec | 子包/section、if/elif/else 与 ifarch/ifnarch、受限宏环境、ExclusiveArch/ExcludeArch、Requires/BuildRequires/Recommends、脚本 uname/if/case、参数/源码赋值及 occurrence 证明图 | 外部/参数宏、rich dependency、未知脚本副作用、include/Lua、损坏结构、预算截断、脚本参数是否真正进入构建 | 完整 RPM/specfile 求值、包可用性、执行构建 |

## `uname -m`

精确且无 wrapper/管道/重定向/额外命令的 `uname -m` 只作为符号 architecture selector：直接使用 ScanContext 的 RISC-V 目标值，不执行命令，也不建模交叉编译误选。不同构建语言按各自支持的条件语义判断，不跨语言套用文件级“RISC-V 优先/通用兜底”的规则。

Autoconf 按 case first-match 和有界 if 判断，`*) exit 1` 是拒绝，不是通用支持。辅助脚本需要有效名称输出及成功退出，配置链还需有实际调用依据；缺少 riscv 字面分支本身不构成缺口。详见 [Autoconf 分析](build-support.zh-CN.md#doc-autoconf-target-support)。

RPM 的补充约束：脚本 `case` 按实际 first-match 顺序判断，不按分支名称推断 fallback；只存在 x86 可选优化，不足以证明必需路径缺口。确定缺口目前来自完整激活的架构许可限制，未证明脚本选择必需性时不升级。脚本中选中的参数/源码赋值也不等同于已被真实构建使用。

目标适配依赖仍保留 Fact，仅在相关展开和上游证明完整时不产生固定 x86 Finding；Recommends 不因 selected 自动阻塞。

<a id="doc-autoconf-target-support"></a>

## Autoconf 配置链

## 输入、配置单元和目标

- 正式发现 `configure`、`config.guess`、`config.sub`、`configure.ac` 和 `.m4`；只读授权工作区，遵守排除规则，拒绝越界软链接。
- 只从已有 target_arch 得到目标 CPU，精确 `uname -m` 符号化为正确 RISC-V 值，不建模交叉误选。未知 OS/release/libc/ABI 不取自宿主机、容器或 x86 compile database；build/host/target 变量不合并。
- 无括号 canonical 与多行字面 AUX_DIR/SUBDIRS 保留声明位置。默认辅助目录只查当前、父级、祖父级，guess/sub 必须同目录；不把多个 vendor 的文件拼成一对。
- 配置单元按目录区分，入口单独记录；子项目与辅助目录声明不冒充真实执行。未输入的远端 x86 产物、未来 bootstrap 输出不能视作已分析。
- 既有 M4 原始事实及 Shell 未选中分支保留，但不能再由旧关键词式 gap 逻辑升级为接受或拒绝。

现有默认排除项包含 `build`。辅助文件若在 `build/autoconf` 且被排除，会报告 unavailable/unknown；可用既有 `--exclude .git` 调整输入范围，不需要新参数。

## 静态语义

支持字面/引号、简单变量与串接、`${v#p}`/`${v##p}`/`${v%p}`/`${v%%p}`，case 的 first-match、嵌套、字面/`*`/`?`/普通字符类/分支 `|`，简单字符串 test/if/elif/else，受限 echo/printf 与 exit，以及工作区内有界字面辅助调用。

| 情况 | 结果 |
| --- | --- |
| 前置 `*) exit 1`，后面有 riscv 分支 | 拒绝；后置分支不能救回 |
| 通用分支输出合法目标名称并成功退出 | 脚本局部接受；不因缺少 riscv 字面报 gap |
| guess 输出传给实际字面调用的 sub，sub 拒绝 | 保留跨文件调用、输出与拒绝链 |
| 只有 exit 0，没有有效辅助输出 | 规范化 unknown |
| 孤立 sub 的 `$1` 未绑定 | 不猜完整 triplet，不升级项目 blocker |
| 未知平台、动态命令、复杂 Shell、预算不足 | unknown，保留事实，不执行项目 |

循环/函数、eval、动态 source、复杂重定向、字段分割/glob 和 case fallthrough 不在子集内。未知副作用会停止后续推演，不能沿用失效环境；原始语法事实仍保留。调用子脚本不隐式改变配置单元工作目录。

预算：4 MiB/文件、64 MiB/全部 Autoconf 读取、256 个入口；AST 100000 节点/64 层，M4 100000 声明，执行 100000 步/128 状态，辅助调用 8 层；图沿用默认 10000 关系/4096 路径，V2 沿用既有显示预算。超限仅降级，不证明拒绝或 ready。

## 兼容输出与真实边界

完整且已绑定的配置拒绝使用既有 missing_riscv_selection_path，属于非阻塞迁移事项；不完整输入使用 build_selection_unknown。接受不表示项目已经编译、链接或测试成功。

源事件的 SHA-256、目录单元、入口、目标和父事件，放入既有 `extensions.org.rvport.kb-scanner.autoconf`，不增加 schema 字段或枚举。既有 reason、中文 suggestion、英文 suggestion_en、源码上下各 20 行和高亮保留，主链没有 classification/assessment 节点。

默认 V2、显式 V1 以及 scan-result.json/scan-report.html/scan.log 不变。HTML 保持现有摘要展示，不增加前端交互。compile database 不能替代脚本原文。

固定的 GCC 4.8.0、14.2.0 所附 GNU 脚本均为 unknown：旧版无 riscv 字面不能单独证明拒绝，新版有分支也不能绕过外部命令和未知平台来证明完整接受。本次是有界静态检查，不是完整 GNU Shell 解释器。

来源、许可证、哈希与人工 oracle 见 [固定样例](../tests/fixtures/autoconf-target/README.md)。独立测试镜像为 rvport-kb-scanner-test:local，不增加依赖、不修改生产镜像/Compose。当前运行命令见开发指南，历史验收见 OpenSpec 中的对应 verification.md；整体及受影响模块均须行/分支至少 90%，真实 parser/CLI 不计入单元门禁。
