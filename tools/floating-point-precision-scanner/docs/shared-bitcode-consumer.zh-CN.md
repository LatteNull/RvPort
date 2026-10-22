# 共享 LLVM BC 消费与运维说明

[English](shared-bitcode-consumer.md) | 简体中文

## 1. 边界

浮点精度扫描器是共享 BC 的只读消费者。它不编译源码生成 BC、不修改 x86 构建结果、
不持有 single-flight 锁，也不轮询 `QUEUED` 或 `GENERATING` 状态。上游构建与编排模块应先
完成一次共享制品生产，并只在 artifact set 进入终态后提交扫描请求。只有 `READY` 或至少
含一个完整成员的 `PARTIAL` 可进入事实提取；`MISSING`、`QUEUED`、`GENERATING` 返回可重试
失败，`FAILED` 返回不可重试的生产失败。这样所有依赖 BC 的分析器都复用同一个不可变
artifact set，而扫描 worker 不会被等待任务占用。

## 2. 请求前置条件

扫描请求始终需要源码输入，用于恢复相同的 C/C++ 编译上下文并生成 AST facts。可选字段
`bitcode_artifact_set` 包含：

- `artifact_root`：manifest 和成员的可信根目录；
- `manifest`：相对可信根目录的 manifest 路径；
- `manifest_sha256`：调用方固定的 manifest 内容摘要；
- `required_profiles`：默认 `source-preserving`，可显式加入 `build-faithful`；
- `source_mapping`：`best-effort` 或 `required`。

如果请求提供 `source_revision`，它必须与 manifest 完全一致。manifest 中的
`compile_commands_sha256` 必须与当前编译输入摘要一致；对 `compile_commands.json` 使用原始
文件字节 SHA-256，对显式翻译单元使用规范化上下文的语义摘要。

## 3. 校验顺序

consumer 在启动 LLVM worker 前按以下顺序拒绝不可信输入：

1. manifest 路径和所有成员路径解析后必须仍在 `artifact_root` 内；
2. manifest SHA-256、JSON 和 schema 必须有效；
3. 源码修订与编译输入摘要必须匹配；
4. 状态、计数、成员和失败记录必须自洽，artifact key 与 `(context_id, profile)` 不得重复；
5. 每个成员必须匹配当前 C/C++ 物理翻译单元、编译上下文和语言；
6. 必需 profile 必须由成功成员或显式失败记录覆盖；
7. BC 和可选 binding sidecar 的大小、预算和 SHA-256 必须匹配。

任何全局身份或完整性错误都返回 `invalid_request`。上游已经记录的单成员生产失败会进入
分层计数并使结果成为 `partial` 或 `failed`，不会被解释为“没有风险”。

## 4. Worker 与兼容性

`fp-ir-worker` 是 C++20 隔离进程，锁定 LLVM reader `21.1.8`、reader contract `1.0`、
extractor contract `1.1` 和 worker protocol `1.1`。Python 主进程在读取 BC 前调用
`--version-json`，任一版本不符都
拒绝执行，不回退到宿主 PATH 中的其他 LLVM。

worker 输出 `LLVMFloatingPointFactBundle@1.1`，覆盖浮点标量/向量相关指令、转换、比较、
call/intrinsic、fast-math flags、target triple、data layout 和 debug location。输出事实有
稳定 ID 和语义摘要，顺序来自确定的 module/function/basic-block/instruction 顺序。worker
输入协议固定为 `1.1`，版本探针同时公开 tool、LLVM、reader、extractor 和 worker protocol
版本，任一不匹配都会在读取 BC 前失败。

调试路径在 Python 边界统一转换为项目相对 POSIX 路径；项目根外路径只保留文件名并增加
`debug_location_outside_project` unknown，绝对 materialization 根不会进入默认输出。每个 IR
bundle 还公开 facts 预算使用量和截断 frontier。wall time、CPU、地址空间、stdout/stderr、
单 BC 与 BC 总字节、IR facts 和 evidence candidates 均有显式预算；超限范围不得被解释为
“没有其他浮点行为”。

## 5. Evidence 与结果解释

源码 facts、IR facts 和 evidence 是三个独立层，不能互相覆盖：

- binding sidecar 只有在 artifact/context、source bundle digest、IR bundle digest 和两端 fact ID
  全部校验通过后，才产生 `explicit-sidecar`/`exact` evidence；
- derived binding 必须同时满足同一 context、稳定函数/符号身份、结构化 debug/inline 与
  AST spelling/expansion 位置以及操作类别兼容，产生 `derived-debug`/`strong` evidence；
- 仅函数名、demangled 文本或源码字符串相似度不会产生 binding；
- 多候选记录到 `ambiguities`，无候选保留 unmatched ID，并产生双语诊断。

`source_mapping=required` 时，任何未绑定 IR fact 都形成阻断性 unknown，使结果至少为
`partial`。`best-effort` 只产生 warning，但仍显式保留 unmatched 集合。核心规则把 binding
作为 typed evidence ref；`x87-excess-precision` 与 `fma-contraction` 在必需 IR 或可靠绑定
缺失时返回 unknown，不把证据缺失解释为不命中。`unsafe-fp-optimization` 会核对有效编译
选项与 build-faithful IR fast-math flags，冲突时同样返回 unknown。

## 6. 故障处置

| 诊断族 | 处置 |
|---|---|
| `artifact_manifest_*` | 重新取得终态 manifest，并固定新的 SHA-256 |
| `artifact_*_mismatch` | 核对源码修订、编译数据库、profile 和上游发布记录 |
| `bitcode_*` | 重新发布该成员；不要原地覆盖已发布 artifact set |
| `ir_worker_version_mismatch` | 使用仓库锁定容器重新构建 worker |
| `ir_worker_failed` | 检查 LLVM 21 BC 兼容性或 verifier/reader 错误 |
| `source_mapping_incomplete` | 补充 debug info 或由上游生成 binding sidecar |

输出使用同目录临时文件、`fsync` 和原子替换发布。失败或中断不会留下可被误读为完整结果的
目标文件。

结果 v2 的 analysis/artifacts 扩展分别公开 artifact、source、IR 和 evidence 四层的
`planned/completed/failed/unknown`，并记录 manifest SHA-256 以及 source/IR/evidence bundle
摘要列表，不引用可变本地路径。只要请求了共享 BC 且全部必需 IR 成员均失败，整体状态就是
`failed`；部分成员成功时才是 `partial`。

## 7. 后端校验阶段与项目 TU 分母

后端交付扫描器前按 manifest 原始 schema 表示校验身份：2.0 不存在
`dialect/standard_source/standard_option`，不得由当前 Java model 注入 null；2.1 必须显式包含这些
字段并通过语言上下文验证。失败阶段固定为 manifest parse/schema/identity、bundle layout、member
integrity、source/compile binding、materialization 或 LLVM worker，并提供稳定中英文原因和脱敏摘要。

覆盖分母使用唯一项目 C/C++ TU，而不是原始 compile database 行数或 manifest planned 的最大值。
raw command、C/C++ candidate、project TU、produced、failed、missing、excluded 分开记录；CMake
CompilerId/ABI probe、TryCompile、链接、归档、其他语言和重复上下文不进入项目覆盖率。生成源码
若无法证明为构建探针，保留为项目候选或显式分类，不仅因位于 build 目录就删除。
