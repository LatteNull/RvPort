# Architecture and frontend boundaries

English | [简体中文](architecture.zh-CN.md)

The public entry is `python -m kb_scanner`. `scan` uses the staged pipeline; `validate-rules` and `list-rules` read JSON knowledge and code-maintained policy only.

The pipeline is:

`ScanRequest → ScanContext → FrontendSnapshot → NormalizedFact → Evidence Graph → Observation → Classification → Assessment → Projector`

## Responsibilities

- `core` owns immutable domain models and contracts. It does not depend on parsers or legacy DTOs.
- Adapters and the pipeline manage inputs, profiles, and scan lifetimes.
- Frontends collect syntax and build information; normalization preserves provenance.
- Analyzers and detectors perform bounded analysis and knowledge queries.
- Classifiers and assessors derive conclusions and project-level static assessments.
- V1 and V2 projectors independently consume the same snapshots. Neither version is converted from the other.

## Parsing and compilation contexts

Tree-sitter provides the baseline. Optional libclang 18.1.3 enrichment uses only directly available compilation contexts. Unavailable or failed Clang analysis retains the baseline and diagnostics, and remains in the completeness denominator. Compilation commands are never executed.

Compiler arguments pass through an allowlist. Plugins, response files, PCH/modules, output-producing flags, and unknown semantic flags are rejected rather than guessed.

Frontends do not produce Findings or readiness. Distinct compilation contexts and positions retain independent identities; ERROR/MISSING nodes create locally incomplete evidence.

## Source locations and lifetime

Positions come only from source byte offsets. Do not read `Node.start_point` or `Node.end_point`. `SourceByteIndex` produces one-based UTF-8 byte columns and handles CRLF and EOF explicitly.

Native Tree-sitter trees and parser objects stay within their parsing lifetime. Later stages receive scanner-owned scalar values and spans, never native parser objects.

Names, comments, and nearby symbols with the same spelling are not proofs of a relationship. Missing or ambiguous evidence remains `unknown`/`partial`.

Distinguish candidates, local confirmations, complete proofs, ambiguity, and unknowns. Relationships/identities must trace to current source or knowledge. Exhausted budgets, missing inputs, and multicontext conflicts remain breaks rather than empty arrays. See [source capabilities](analysis-capabilities.md), [build support](build-support.md), and the [result contract](schema-v2-design.md).
