# Memory Order Analyzer documentation

English | [简体中文](README.zh-CN.md)

Start with the [tool README](../README.md), then use these guides.

| Document | Contents |
|---|---|
| [Unified project analysis](UNIFIED_PROJECT_ANALYSIS.md) | Project entry point |
| [External bitcode](EXTERNAL_BITCODE_INGESTION.md) | External BC contract |
| [Degraded analysis](DEGRADED_SOURCE_ANALYSIS.md) | Failures, degradation, and support matrix |
| [Semantic analysis](semantic-analysis.md) | Semantic facts, effect summaries, AST/IR, and objects |
| [Thread analysis](thread-analysis.md) | Thread entries, lifecycles, and RAII synchronization |
| [Demand analysis](demand-analysis.md) | ExecutionRoot, demand-driven analysis, and candidate graphs |
| [Publication analysis](publication-analysis.md) | Single publication, fences, RMW, and CAS |
| [Result projection](MEMORY_ORDER_FINDING_SCHEMA.md#doc-memory-order-finding-schema) | Findings and source context |
| [Development](development.md) | Docker development and quality checks |

## Specifications

Requirements, designs, and change records are in [OpenSpec](../openspec).
