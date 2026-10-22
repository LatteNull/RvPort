# Autoconf 人工 oracle / 固定来源

本目录是只读测试数据，不是构建输入；不得执行其中脚本。完整来源、固定提交和 SHA-256 见 `oracle.json`。GNU 原文及 GPLv3/附加许可保留在 `gnu/`，libarchive 原文及许可证在 `libarchive/`。固定 LF，不重新格式化第三方原文。

## 独立人工判定

- `gcc-4.8.0` 的两份脚本没有 riscv 字面；这不足以单独证明拒绝。完整脚本依赖外部命令/动态 Shell，因此本次静态分析必须 unknown。
- `gcc-14.2.0/config.guess` 第 1089 行有 RISC-V Linux 分支，输出仍依赖 `$LIBC`；`config.sub` 第 1254 行含 riscv CPU 候选。字面存在不证明整个输入和规范化链已通过。两份脚本前置外部命令也超出本次子集，期望 unknown，不得伪造 accepted。
- libarchive 的 `configure.ac` 第 26 行指定 `build/autoconf`，第 92 行无括号 `AC_CANONICAL_HOST`。输入没有实际辅助脚本，期望声明及 unavailable/unknown，不猜测未来 bootstrap 内容，不判为 RISC-V 不支持。

`tests/test_autoconf_target_component.py` 的独立小型 oracle 另外覆盖：first-match 的 wildcard 拒绝、显式 riscv 拒绝、通用输出接受、未知 OS、if/elif、参数截取、空输出、guess 成功后 sub 拒绝及恶意命令。这里不使用 scanner 的输出反向生成期望值。

## 资料依据

- [GNU Autoconf 2.72：规范化与 build/host/target](https://www.gnu.org/software/autoconf/manual/autoconf-2.72/html_node/Canonicalizing.html)
- [GNU Autoconf 2.72：辅助脚本搜索与生成](https://www.gnu.org/software/autoconf/manual/autoconf-2.72/html_node/Input.html)

本地 fixture 只截取 libarchive 的配置输入，没有其余项目源码；完整项目回归使用验证记录中指定的只读历史项目目录。
