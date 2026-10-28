# Result contract and source context

English | [简体中文](MEMORY_ORDER_FINDING_SCHEMA.zh-CN.md)

<a id="doc-memory-order-finding-schema"></a>

MemoryOrderFindingProjection provides self-contained backend/frontend display objects. It uses the fact + conclusion + occurrences + evidenceChain consumption shape familiar from KB Scanner v2, enabling shared list/detail/graph/context components. It has an independent schema, org.rvport.memory-order-analyzer.* provenance, and memory-order vocabulary. It imports no KB Scanner package and carries no RISC-V, archReachability, knowledge-match, or porting semantics.

## Three collections

The unified report uses the same projection shape in mutually exclusive collections:

- findings[]: conclusion.verdict=risk, only formal P4/A6 risks with closed evidence.
- source_candidates[]: verdict=source-candidate, status=unknown, AST-only/source candidates with nonempty breaks.
- discharged_assessments[]: verdict=discharged-within-bounded-model, bounded discharge only, never safety.

inconclusive describes formal assessments/project states that cannot be projected reliably. Missing evidence creates projection frontiers rather than silently putting upstream risk/discharge into the wrong collection.

## Top-level structure

当前生产者输出 `schemaVersion=3.0`；保留 2.0 读取。3.0 增加 `conclusion.evidenceLevel` 并允许 confidence=null；未验证候选为 info、非阻断、待核实。每项保留 id/scopeId/semanticDigest、fact、conclusion、occurrences/primaryOccurrenceId、evidenceChain。完整的新旧版本、inconclusive 集合和历史适配规则见[中文协议说明](MEMORY_ORDER_FINDING_SCHEMA.zh-CN.md#30-与历史-20-的兼容)。

Stable IDs/digests exclude absolute paths, time, backend task IDs, scheduling order, and translation text. Provenance fixes kind/id/producer/schemaVersion/digest; producer belongs to this tool's namespace. Schema/semantic validators reject unresolved step/occurrence/artifact references.

## Nodes, edges, and breaks

Node kinds include thread-creation, callback-binding, execution-root, call-path, thread-instance, mhp, memory-access, object-provenance, byte-range-overlap, mutex-region, atomic-event, reads-from, modification-order, release-sequence, synchronization-proof, synchronization-gap, source-fact, and conclusion.

Edges express adopted relationships only: callback/root binding, reachable, instance-of, may-happen-in-parallel, accesses, overlaps, protected-by, reads-from, precedes-in-mo, extends-release-sequence, synchronizes-with, supports, supports-candidate. P2 order, P3 RF candidates, R2 candidates, lexical proximity, and MemorySSA alone do not establish SW/HB.

primaryPath connects rootStepId to the conclusion through actual edges; related branches remain in steps/edges. Complete chains have no known breaks. Partial/unknown/ambiguous/source-candidate chains require at least one. Truncation itself is a break; a truncated empty graph cannot be complete.

## Source positions and windows

Source-bearing facts/occurrences/steps use project-relative POSIX paths (reject absolute paths, `..`, backslashes, symlinks/escaping resolutions), one-based end-exclusive spans and exact highlights, sourceSha256 and snapshot artifact references, plus actual line numbers/text in context.lines[].

Default context is ±20 lines, limited to 256 lines/65,536 characters per location with hits prioritized. Read only analysis-time snapshots matching fact digests, never current same-name workspace files. Missing debug, IR-only input, absent SourceIRBinding, digest mismatch, invalid spans, read failures, and truncation produce partial/unavailable and breaks, never fabricated source/positions/highlights. Full snapshots deduplicate by SHA-256; backends may expand context through the artifact index.

## Frontend example

```json
{
  "id": "org.rvport.memory-order-analyzer.finding:...",
  "conclusion": {
    "verdict": "source-candidate",
    "status": "unknown",
    "title": "源码级内存序候选",
    "title_en": "Source-level memory-order candidate"
  },
  "primaryOccurrenceId": "occurrence:...",
  "evidenceChain": {
    "rootStepId": "step:...",
    "primaryPath": ["step:...", "step:..."],
    "steps": [],
    "edges": [],
    "breaks": [{"reasonCode": "missing-ir-binding"}],
    "impactStepIds": [],
    "budget": {"truncated": false}
  }
}
```

Render verdict/status/breaks and bounded scope explicitly. Colors, exit 0, and zero Findings must not mean thread-safe. Machine contracts are schemas/memory_order_finding.json and schemas/unified_project_analysis.json.

<a id="doc-finding-source-context"></a>

## Source-reference resolution

These projection rules do not alter memory-order rules or formal conclusions.

- Source candidates resolve only facts referenced by their own physical_tu_ids and node_ids/relation_ids.
- Publication/discharged assessments resolve only artifact_key + id events in assessment evidence.
- Advanced atomics follow p4_protocol_id to the current Scope's publication graph and events. Without that chain, retain no location rather than search unrelated graphs.
- AST prefers expansion locations while retaining spelling; IR uses debug inline chains.
- Map absolute paths through manifest source roots; reject outside-root locations. Missing filenames do not imply the primary TU; same-name files do not match by suffix. Cross-file endpoints degrade to a single-character start span, not a cross-file range.
- Backend profiles explicitly map local/remote source roots to `.` in path_map. After primary-source digest validation, the tool snapshots from one unique local root and restores original relative paths. Multiple roots are not guessed. Equal macro-argument endpoints become single-character highlights; reversed spans are rejected.

## Snapshots and display

Before analysis, snapshot the main source and project .h/.hpp/.hh/.hxx/.inc/.inl files. Header limits are 8 MiB per file and 64 MiB total; reject escaping symlinks. Limits appear as snapshot failures/unavailable context. Unsupported extensions or missing snapshots never produce invented snippets. Verify snapshots by content SHA-256.

Each context honors request context_lines/context_characters budgets and returns true line numbers/text/highlights/completeness. span.end is exclusive; column 1 of the next line does not highlight that line. Sort/deduplicate locations by expansion priority, relative path, line/column, and TU; preserve primary/occurrence association. Source-access steps retain their own locations; other layers without direct source evidence keep empty source.

Missing locations do not change risk judgments. Formal risk/discharge retains verdict with a source gap; AST-only remains candidate. Unavailability explanations are bilingual. No new required JSON fields are added. Finding semantic seeds remain unchanged; corrected locations change occurrence/step identities. Unified caches include source_projection_revision=2 to avoid old snippetless reports.

## Regressions

Inside the Linux development container, run isolated units with `PYTHONPATH=python python3 -m pytest -q tests/unit`.

Real Clang coverage: `PYTHONPATH=python MOA_WORKER=/output/build/moa-worker python3 -m pytest -q tests/integration/test_finding_source_context.py`. It requires memory-order-source-worker beside moa-worker and checks real absolute-header-to-snapshot mapping. It does not replace isolated units or formal backend API acceptance.
