# KB Scanner result contract

English | [简体中文](schema-v2-design.zh-CN.md)

## Design

Schema v2 uses a single Finding as the detail boundary. Every `findings[]` item contains its own `fact`, `conclusion`, `occurrences[]`, and `evidenceChain`. Opening a Finding returns the full main chain, branches, breaks, hit locations, and line-by-line code context without reconstructing them from top-level Explanations, Catalogs, or internal scanner snapshots.

List and detail views are separate projections. Lists read the Finding ID, primary fact location, and conclusion summary; details return the complete Finding. `scan-result.json` retains complete `findings[]` for offline auditing, but the backend must persist queryable individual Findings rather than replacing them with one opaque JSON field containing the entire report.

```text
Finding
├─ fact: static facts actually found by the scanner
├─ conclusion: severity, actionability, blocking, porting reasons and suggestions
├─ occurrences[]: all hit locations, configurations, and selection states
└─ evidenceChain
   ├─ primaryPath[]: default detail display order
   ├─ steps[]: build, source, macro nodes, and side-branch knowledge
   ├─ edges[]: node relationships and candidate/alternative branches
   └─ breaks[]: missing evidence, conflicts, ambiguity, cycles, or budget truncation
```

## Schema 1.0 compatibility baseline

The scanner defaults to `schemaVersion: "2.0"`. Consumers that depend on the old fields must explicitly select `--schema-version 1.0`. Each scan produces the same three named artifacts for only the selected version. V2 failures never silently fall back to V1, and there is no V1-to-V2 conversion layer. The backend and frontend use the current V2 contract for lists, details, and evidence chains.

## Field responsibilities

| Field | Represents | Does not represent |
|---|---|---|
| `fact` | Actual matched fact kind, symbol, text, primary location, and provenance | Severity, blocking, or project readiness |
| `conclusion` | Classification, severity, actionability, blocking, reasons, suggestions, and static Assessment impact | Raw code evidence |
| `occurrences[]` | Aggregated source/build/test locations, configurations, and selection states for one Finding | Finding counts based on occurrence counts |
| `evidenceChain` | Actual relationship subgraph from build arguments/selection to source and macro invocation/expansion, with knowledge on a side branch | Classification/assessment stage nodes or unrelated project evidence |
| `summary` | Project counts per Finding, static readiness, and completeness | Readiness inferred from zero hits |
| `diagnostics[]` | Structured scan-level or Finding-related errors, aggregate counts, and references | Machine fields encoded in prose strings |

## Code context and positions

Every code-bearing fact, occurrence, and step uses the same `source` shape: a normalized project-relative path; a full one-based, end-exclusive span; `context.lines[]` with real line numbers; and precise `highlights[]`. Macro calls, definitions, replacements, intrinsics, and Makefile selectors each retain their own locations; never copy another step's location.

The default window includes 20 lines before and after the hit, typically 41 lines for a single-line hit. Each location is capped at 256 lines and 65,536 characters. Prioritize the hit, then balance nearby preceding/following context. Read failures or exhausted budgets retain the original span and mark context `partial`/`unavailable` with a reason. Long lines may be omitted, but columns must never be fabricated and highlights must remain in bounds. File-line and span-projection caches are shared within one scan only. The backend's separate code-context endpoint handles expanded context.

## Chains and completeness

`primaryPath[]` supplies a deterministic default display order; clients need not search arbitrary graphs. `steps[]` contains all relevant candidate and supporting objects, `edges[]` preserves actual Relation/ProofPath provenance, and `breaks[]` makes discontinuities explicit.

New producers must include the current hit anchor in the primary path and connect actual endpoints rather than choosing representative nodes by kind. Multiple macros of the same kind remain distinct. `guarded_by` may render as condition → guarded object, with original endpoints/direction retained in `org.rvport.kb-scanner.source-chain.incoming`. Structural nodes without positions may collapse only while preserving every consecutive relationship. Unrelated occurrences or same-name candidates cannot form a complete path.

Producers no longer emit `classification`/`assessment` stages; `impactStepIds` is always `[]`. Read decisions from `conclusion`/`summary`. A `knowledge_match` appears only on an actual `matches_knowledge` side branch, never the main path. New readers still accept historical V2 stage nodes; producers do not continue emitting them.

- `complete`: every displayed step/edge on the relevant main path is complete, with no known break. This proves a local source relationship, not exhaustive callers or successful RISC-V compilation.
- `inactive`: complete proof that the target configuration does not select the x86 path. It is guarded/non-actionable, not independent proof of project readiness.
- `partial`: some evidence exists, but inputs, references, or budgets are insufficient.
- `ambiguous`: multiple verifiable candidates cannot be uniquely selected.
- `unknown`: static analysis cannot establish a sufficient conclusion.

`partial`, `ambiguous`, and `unknown` require at least one break. Empty arrays, zero counts, and missing fields must not imply “no problem.” Cross-field rules are frozen in `schemas/scan-result-v2-reference-rules.json`.

## Knowledge and static scope

A knowledge step contains only the compact projection actually referenced by the Finding: entry ID, category, symbol, producer, source identity/digest, and provenance. It does not copy an entire compiler fact file. V2 changes report projection, not the current frozen `clang-x86-entries.json` and `gcc-x86-entries.json` bytes, six-category counts, or sources.

Top-level scope always declares `staticAnalysisOnly=true`, `compiled=false`, `linked=false`, and `testsExecuted=false`. Terms such as x86-only, blocking, and ready-like describe static proofs only. Real RISC-V compilation and testing belong to subsequent RvPort stages. OS, kernel, syscall, driver, and board-level porting are outside this schema.

## Determinism and extensions

Ordering for Findings, occurrences, steps, edges, breaks, Diagnostics, context lines, and highlights is frozen in `schemas/scan-result-v2-vocabulary.json`. IDs must not contain absolute checkout roots, timestamps, randomness, object addresses, or traversal order. Core objects have closed fields. Extension keys must match `org.rvport.kb-scanner.<capability>`; unrestricted `trace` fields must not return.

## Consumer compatibility

The version remains 2.0 and the Finding envelope is unchanged. Older strict consumers still need coordinated model/validator updates; this is not entirely transparent:

- Accept `impactStepIds: []`. Read conclusions from `conclusion` and `summary`, not classification/assessment chain stages.
- Render actual edges referenced by `primaryPath`. Do not group or deduplicate by node kind; repeated macros are valid. Knowledge is a side branch, not a mandatory final node.
- Expect ±20 lines by default and hard limits of 256 lines/65,536 characters. Use `context.lines[].line` and highlights directly; do not assume contiguous lines or recompute truncated columns.
- Display breaks for partial/unknown/ambiguous chains. A single-node or local complete chain is not exhaustive build/call-path coverage; compilation still needs validation.
- Keep historical stage kinds in reader vocabulary. New producers do not emit them; old stage nodes must not be presented as source code.

`org.rvport.kb-scanner.source-chain.incoming` is an optional audit extension containing collapsed relationship IDs, original entity endpoints, and directions. Basic rendering still depends only on existing steps/edges/source.

## Bilingual suggestion contract

The version remains `2.0`. New producers emit both fields in each `finding.conclusion`:

| Field | New reports | Historical reports |
|---|---|---|
| `suggestion` | Nonempty Chinese suggestion, displayed by default HTML | Preserve original text, including historical English |
| `suggestion_en` | Nonempty English equivalent with the same degree of certainty | May be absent; do not fabricate a translation or null |

`--locale` does not swap these fields. Titles, reasons, evidence-node descriptions, status codes, diagnostics, and logs are outside this localization change. HTML adds neither an English column nor a language switch. Consumers needing English read `suggestion_en`; for historical absence, use the original text or their normal UI fallback.

Compatibility is directional: new readers accept old reports, but old closed models/schemas reject the added field. Upgrade the [schema](../schemas/scan-result-v2.schema.json) and Conclusion model before connecting a new producer.

- Generic readers allow omission of the English field only. Explicit null, empty/whitespace-only strings, and non-string values are invalid.
- Historical round trips use existing `render_json()` or `model_dump(mode="json", exclude_none=True)` to preserve omission semantics.
- Before publishing all three artifacts, current producers additionally require both fields to be nonempty. Historical reader tolerance cannot bypass producer requirements. Failures follow the existing projection-failure path without partial publication.
- Readers do not reject historical reports using a Chinese-character regex or infer natural-language equivalence. Paired templates and human-authored expectation tests establish language and certainty for new output.

Suggestions follow the existing conclusion: gather evidence for unknown/partial/ambiguous results; retain exclusion conditions for inactive results; verify hints; check target applicability for non-blockers; address selected x86 dependencies for blockers; and separately explain build-selection and test-coverage gaps. Wording stays within static scope and never claims actual compilation or testing occurred.

Human-frozen wording is in the [bilingual expectations](../tests/fixtures/bilingual-suggestions/expected-pairs.json). Allowed differences are limited to the two suggestion fields, as recorded in the [differential ledger](../tests/fixtures/bilingual-suggestions/report-differential.json). Historical reports and ledgers are not rewritten. V1, facts, classification/assessment, IDs, source chains, contexts, summary, diagnostics, and logs are unchanged by this suggestion change.
