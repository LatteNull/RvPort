# Generated x86 Entry Sources

本目录保存从编译器源码中收集的 x86-only / x86-specific 入口词表。

## Clang

来源：

- 本地 sparse checkout: `vendor/llvm-project/clang/lib/Headers`
- 本地 sparse checkout: `vendor/llvm-project/clang/include/clang/Options/Options.td`
- 上游仓库: `https://github.com/llvm/llvm-project`
- 生成脚本: `tools/collect_clang_x86_entries.py`
- 输出文件: `clang-x86-entries.json`

当前统计：

```text
headers = 125
intrinsics = 7563
builtins = 1993
vectorTypes = 10
platformMacros = 5
compilerFlags = 216
```

说明：

- Clang 用于收集 builtin headers 中暴露的 x86 intrinsic、header、builtin 和向量类型。
- `compilerFlags` 是从 `Options.td` 中的 `m_x86_Features_Group` / `m_x86_AVX10_Features_Group` 自动抽取的，覆盖 `-mavx2`、`-mno-avx2`、`-msse2` 等 Clang x86 feature flags。
- 规则通过 `generatedSet` 引用词表，而不是把几千个函数名手写进 YAML。

## GCC

来源：

- 本地 sparse checkout: `vendor/gcc/gcc/config/i386`
- 上游仓库: `https://github.com/gcc-mirror/gcc`
- 生成脚本: `tools/collect_gcc_x86_entries.py`
- 输出文件: `gcc-x86-entries.json`

当前统计：

```text
headers = 120
intrinsics = 7602
builtins = 3438
vectorTypes = 10
platformMacros = 47
compilerFlags = 225
```

说明：

- GCC 主要补充 `gcc/config/i386` 下的 intrinsic headers、GCC builtin 和 `i386.opt` 中定义的 x86 `-m*` 编译参数。
- `compilerFlags` 是从 `i386.opt` 自动抽取的，覆盖范围比手写 `-mavx2`、`-msse` 更完整。

## 使用方式

规则文件可以通过 `generatedSet` 引用集合：

```yaml
match:
  any:
    - call:
        generatedSet: "intrinsics"
    - text:
        generatedSet: "compilerFlags"
```

规则引擎会合并本目录下所有 `*-x86-entries.json` 文件中的同名集合。
