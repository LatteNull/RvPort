# 共享 LLVM Bitcode 制品协议 v2

[English](shared-llvm-bitcode-artifact-contract-v2.md) | 简体中文

`SharedLlvmBitcodeArtifactSet@2.1` 是 RvPort 平台级的中立 BC 合同。它由 source/x86 构建后的非阻断阶段产生，保存在对象存储中，并由后续浮点精度和强弱内存序分析复用。消费者兼容读取 `2.0`，但新 producer 只发布 `2.1`。

## 语言标准上下文

每条 record 记录 `standard`、`dialect`、`standard_source` 和 `standard_option`。其中基础标准保留 C89/C90、C99、C11、C17/C18、C++98、C++03、C++11、C++14、C++17 和 C++20 的真实语义；C23/C++23 可按当前 Clang 能力接收，但不属于首轮规则准确率承诺。GNU 别名通过 `dialect=gnu` 表达。没有 `-std` 时标记为 `compiler-default` 并保留生产编译器身份，不得猜测或伪装为 C17/C++17。

`failed`、`missing` record 与 `produced` record 一样保留 physical TU、context、源码、compile record digest 和标准上下文，使消费者可以在 BC 不完整时继续建立完整 AST 分母。

## 消费模式

- `AST_BC_COMPLETE`：所有计划 TU 均有通过校验的 BC。
- `AST_BC_MIXED`：只有部分 TU 有 BC；所有 TU 仍执行 AST 规则。
- `AST_ONLY`：BC 缺失、全部失败或 Worker 校验失败；分析任务继续执行，IR 专属规则降级为 unknown/not-applicable。

## 身份与边界

- manifest 不包含项目、源码版本、构建记录、数据库或对象存储主键，这些关联只保存在后端数据库中。
- 所有身份使用 UTF-8 canonical JSON 的 SHA-256。对象键排序，数组按 canonical JSON 排序；路径统一为 POSIX 相对路径。
- `generated_at`、诊断、bundle 外部哈希和业务主键不参与 artifact-set 身份。
- `raw_compile_commands_sha256` 证明单次原始输入字节，作为审计证据保留但不参与语义身份；`normalized_digest` 表达移除受控部署根后的稳定编译语义，并参与 `semantic_digest` 与 `artifact_set_id`。
- 平台 `artifact_key` 不是分析器内部 ArtifactKey。分析器必须依据自身 extractor/schema/policy 重新计算内部身份。

## Bundle 布局

```text
manifest.json
records/<record_id>.json
bitcode/<record_id>.bc
sidecars/<record_id>/*
scopes/<scope_id>.json
```

每个唯一的规范化编译上下文均产生 record，收敛到相同最终 `record_id` 的重复条目只计一次。成功项为 `produced`；缺失输入为 `missing`；编译、验证、预算或超时错误为 `failed`。失败记录不得从计划分母消失。

当前 profile 为 `source-preserving@1`，保留逐 TU raw module、debug/source correlation、浮点 IR、原子 ordering、`syncscope`、fence、target/DataLayout 和 linkage 信息。无法由 compile database 证明目标闭合时，生产器按 target triple 创建 `closed=false` 的 fallback scope。

## 消费者兼容矩阵

| v2 字段 | 浮点扫描器 | memory-order-analyzer |
|---|---|---|
| record/status/bitcode | 选择 produced 成员并保留失败分母 | 映射 ExternalBitcodeArtifactRecord，保留 produced/missing/failed |
| producer/target | 校验 LLVM reader 和浮点 target 语义 | 原样映射 producer、target triple、DataLayout、ABI |
| language/standard/optimization/debug/module_kind | 构建分析上下文 | 原样映射外部 record 必填字段 |
| source/compile_record_digest/input_digests | 源码定位和 provenance | 原样映射，缺口保持 partial |
| scopes | 可用于项目级聚合 | 映射 ExternalBitcodeBundleManifest scope；开放 scope 产生 partial/frontier |
| capabilities | 选择 `fp.*` 与 source correlation | 选择 `memory.*`、target、debug 与 linkage |
| artifact_key | 平台制品身份 | 仅作为外部引用，禁止冒充分析器内部 ArtifactKey |

后续 adapter、对象存储 materializer 和分析任务运行时不属于本协议升级。分析工具直接在 `backend-worker` 中作为本地子进程运行，不需要独立扫描容器或 `docker.sock`。
