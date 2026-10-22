# Reviewed validation corpus

`reviewed-case-families.json` 是人工评审依据；`reviewed-corpus-v1.json` 逐项固定 10 条规则的
正例、反例、unknown、suppression、预算失败和边界 case。`reviewed-observed-v1.json` 是锁定
fixture harness 的接受基线，不由待测指标算法即时生成。任何 oracle 或 observed 变更都必须在
代码评审中解释规则证据和差异，不得直接用失败运行覆盖 golden。

语料只覆盖 C11、C17、C++17、C++20 以及 x86_64 Clang 21 → RISC-V LP64D Clang 21；
不代表业务容差，也不替代后续真实工程差分验证。
