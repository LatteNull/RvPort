# KB Scanner 架构

[English](architecture.md) | 简体中文

正式入口为 `python -m kb_scanner`。`scan` 使用 staged pipeline；`validate-rules` 和 `list-rules` 只读取 JSON knowledge 和代码维护的 policy。

## 数据流与职责

`ScanRequest → ScanContext → FrontendSnapshot → NormalizedFact → Evidence Graph → Observation → Classification → Assessment → Projector`。

| 目录 | 职责 |
|---|---|
| `core` | 不可变领域模型、统一上下文和结构化 Diagnostic，不依赖 parser 或旧 DTO |
| `adapters`、`pipeline` | 输入边界、显式 profile 和阶段生命周期 |
| `frontends`、`normalization` | 读取源码、构建信息、编译记录，保留 producer/context provenance |
| `analyzers`、`detectors` | 有界关系、知识匹配、候选及用途证明 |
| `classifiers`、`assessors` | 风险分类、完整性与静态 readiness |
| `projection` | 独立 V2/V1 Projector，从同一 snapshots 发布报告，不互相转换 |

## C/C++ 前端

Tree-sitter 提供容错 baseline；编译数据库是可选增强输入。只有直接 compilation context 才调用 libclang 18.1.3；失败保留 baseline 和 Diagnostic，不删除失败分母。编译记录只读，不执行其 command。

参数白名单拒绝 plugin、response、PCH/modules、输出和未知语义选项。前端不负责生成 Finding 或 readiness。多编译上下文及不同位置保留独立身份；ERROR/MISSING 形成局部不完整证据。

源码位置统一使用原始字节偏移。Tree-sitter Node 的 `start_point`/`end_point` 不可读取；`SourceByteIndex` 负责一基 UTF-8 字节列和 CRLF/EOF。Tree 仅在当前解析阶段存活，跨阶段仅保存自有值和字节范围，防止原生对象生命周期错误。

## 证据与结论

名称、注释、邻近代码和同名符号不能单独构成使用证明。明确区分 candidate、局部确认、完整证明、歧义与 unknown。关系及身份必须可追溯到当前源码或知识来源。预算耗尽、缺失输入及多上下文冲突保留为断点，不以空数组代替。

具体支持范围见 [源码能力](analysis-capabilities.zh-CN.md)、[构建支持](build-support.zh-CN.md)，输出合同见 [结果协议](schema-v2-design.zh-CN.md)。
