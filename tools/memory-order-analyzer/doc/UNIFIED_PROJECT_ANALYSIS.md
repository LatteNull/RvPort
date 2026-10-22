# Unified project-level memory-order analysis

English | [简体中文](UNIFIED_PROJECT_ANALYSIS.zh-CN.md)

analyze-project is the only production backend entry point. It accepts UnifiedMemoryOrderAnalysisRequest v1, reads its referenced ExternalBitcodeBundleManifest, isolates explicit Scopes, and emits UnifiedMemoryOrderAnalysisReport v1. Advanced CLIs remain for development, diagnosis, and protocol regressions; backends need not invoke them sequentially.

## Input boundaries

- Project is the task aggregation boundary; Scope is the cross-TU semantic boundary; BC/TU is the indivisible input atom.
- scope_selection is all or sorted, deduplicated scope_ids.
- Bundles declare planned TU denominators, BC digests, producer/LLVM versions, target, DataLayout, ABI, standard, profiles, physical TUs, source lineage, Scopes, and production failures.
- Evidence with different targets/DataLayouts/ABIs/Scopes aggregates side by side at project level, never links/merges into one program verdict.
- Compilation databases only assist external source profiles/SourceIRBinding; this entry neither generates BC nor infers complete Scope from them.

Production forbids GCC/Clang drivers, -emit-llvm, linkers, CMake configure/build, network, SSH, and target execution. Only pinned LLVM readers/analysis workers and source workers may execute.

## Request and execution DAG

Public requests expose bundle, Scope selection, source_assistance, explicit roots, fixed policy, budgets, cache/resume, deadline, and cancel file. Internal stage switches are not public contract.

```text
bundle preflight / external BC ingestion
  ├─ AST source facts（independent for every planned TU）
  └─ ModuleFacts / LLVM lightweight index
          ↓
ExecutionRoot + ThreadEntry bootstrap
          ↓
R3 bounded demand worklist
          ↓
P2 effects + P3/A3 lifecycle + A4 synchronization + A5 provenance
          ↓
R2 concurrent-access candidates
          ↓
P4 publication + A6 fence/RMW/CAS overlay
          ↓
Finding projection + Scope/project aggregation
```

UnifiedAnalysisPlan fixes each Scope's stage IDs/versions/producers, input/output kinds, dependencies, applicability, budgets, caches, and failure policies. Task IDs, absolute outputs, time, scheduling, and cache counts do not enter semantic digests. Root/direct-call/callback/recursion expansion uses bounded monotonic worklists. Exhausted budgets create nonempty frontiers without all-defined fallback.

## AST/IR modes

AST is an independent fact layer for every planned TU, not a late BC-failure fallback.

| Mode | Evidence | Allowed external conclusions |
|---|---|---|
| ast-ir | AST plus compatible IR | Existing bounded formal analysis |
| ir-only | Available IR, absent/untrusted AST | Retain IR provenance; source locations may be unavailable |
| ast-only | Trusted AST, unavailable BC/IR | Source-only candidates, partial/unknown, breaks |
| failed | Neither available/trusted | Failed or candidate-relevant frontier |

source_assistance=auto uses available trusted AST; required propagates relevant missing AST as incomplete; disabled explicitly uses IR only. Reject AST with fatal/recovery diagnostics, profile conflicts, or source-digest mismatches. AST-only establishes no runtime object identity, alias/noalias, byte overlap, ThreadInstance, RF/MO/release sequence, SW/HB, formal risk, or bounded discharge.

Propagate completeness through candidate dependency slices. Proven-unrelated failed TUs do not degrade independent candidates; relevant or uncertain relevance does. Zero candidates cannot conceal unanalyzed/unknown relevance.

## Scope isolation, recovery, failures

The coordinator runs independent Scopes with bounded concurrency and publishes in stable Scope-ID order. One Scope/stage failure does not erase completed Findings elsewhere. ScopeAnalysisExecutionRecord retains TU modes, stages, denominators, diagnostics, and frontiers.

Cache keys bind normalized requests, bundle/Scope, record digests, stage/version, and budgets. Cache only complete dependency-closed Scope payloads and immutable artifacts. Reads revalidate namespace/key/payload digest/schema/Findings/artifact paths and digests. Partial, cancelled, crashed, damaged, or conflicting entries cannot be successful hits. Hits affect runtime metadata only.

Check deadline/cancel files cooperatively at ingestion, Scope, and major-stage boundaries. Stop scheduling new Scopes while atomically publishing completed results; unfinished nodes never enter success caches. Build fresh output in a same-directory temporary tree, then replace once a successful or auditable stopped report is complete. Reject existing target directories.

## Outputs and backend responsibilities

Outputs include request.json/plan.json/report.json; scopes/<scope>/execution.json; individual JSON under findings/, source-candidates/, discharged-assessments/; source-snapshots/<sha256>/source with digest-bearing artifacts.json; and raw stage facts/reports under data/ for offline audits.

Backends prepare bundles/optional source requests, run one command, finalize tasks from exit/report state, preserve complete output, and optionally persist Findings individually. They must not reconstruct internal stage requests or infer safety from one empty array. Lists read conclusion summaries; details read self-contained evidenceChain. Expanded context must use analysis-time snapshots through artifact index/source digest.

## Project verdicts and exit codes

| Exit | Verdict | Meaning |
|---|---|---|
| 0 | no-finding-within-supported-model | Selected relevant slices complete, no formal risk in supported model |
| 3 | risk | Selected relevant slices complete, formal risk exists |
| 2 | inconclusive | Partial/unknown/ambiguous/AST-only/open Scope/budget/cancel/retained failure; takes precedence over risk |
| 1 | failed | Invalid request, no selected Scope can be established, or all evidence failed |

Complete, exit 0, zero Findings, and discharged-within-bounded-model must never be presented as whole-program safety.
