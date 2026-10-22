# 内存序分析器文档

[English](README.md) | 简体中文

先阅读 [工具 README](../README.zh-CN.md)，再按需要进入下列手册。

| 文档 | 内容 |
|---|---|
| [统一项目入口](UNIFIED_PROJECT_ANALYSIS.zh-CN.md) | 统一项目入口 |
| [外部 BC 合同](EXTERNAL_BITCODE_INGESTION.zh-CN.md) | 外部 BC 合同 |
| [失败、降级与支持矩阵](DEGRADED_SOURCE_ANALYSIS.zh-CN.md) | 失败、降级与支持矩阵 |
| [语义事实、效果摘要、AST/IR 与对象](semantic-analysis.zh-CN.md) | 语义事实、效果摘要、AST/IR 与对象 |
| [线程入口、生命周期与 RAII 同步](thread-analysis.zh-CN.md) | 线程入口、生命周期与 RAII 同步 |
| [ExecutionRoot、按需分析与候选图](demand-analysis.zh-CN.md) | ExecutionRoot、按需分析与候选图 |
| [一次性发布、fence/RMW/CAS](publication-analysis.zh-CN.md) | 一次性发布、fence/RMW/CAS |
| [结果投影与源码上下文](MEMORY_ORDER_FINDING_SCHEMA.zh-CN.md#doc-memory-order-finding-schema) | 结果投影与源码上下文 |
| [Docker 开发与质量验证](development.zh-CN.md) | Docker 开发与质量验证 |

## 规范

需求、设计和变更记录见 [OpenSpec](../openspec)。
