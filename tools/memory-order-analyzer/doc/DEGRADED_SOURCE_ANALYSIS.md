# Degraded source analysis and conservative completeness

English | [简体中文](DEGRADED_SOURCE_ANALYSIS.zh-CN.md)

`add-degraded-source-analysis` adds an independent A2 wrapper over P1–P4/A1. It retains trustworthy source facts when a TU cannot produce/analyze BC, and prevents unmodeled mutex/RAII/synchronization wrappers from being mistaken for proven absence of synchronization. It changes neither semantics nor cache identities of ModuleFacts v2, EffectSummary v1, ThreadContextGraph v1, SinglePublicationProtocolGraph v1, or A1 artifacts.

## 1. Supported scope

- Compatible GCC/G++ and Clang/Clang++ records only; Windows/MSVC/clang-cl are rejected.
- Separate C11/C17/C++17/C++20 profiles. C covers C linkage, direct pthread, global/static objects, struct/union fields, macros, _Atomic, and <stdatomic.h>, without C++ AST/library models.
- C++ can observe pthread, atomic, and lock_guard/unique_lock/scoped_lock types, but A2 establishes no RAII lock regions/synchronization edges.
- Compile-only/source-analysis-only: no linking, target execution, CMake configuration, networking, or implicit scope expansion.

Compilation databases optionally supply real per-TU AST/source-worker arguments, not BC generation. Requests pin digests for source requests, external records, IR-binding requests, ModuleFacts, and optional P3/P4 artifacts. Missing BC/reader failures may retain AST-only candidates as partial/unknown. No automatic latest-file selection occurs.

## 2. Protocol and artifacts

See [protocol](../protocols/degraded-source-analysis-protocol.json) and [strict schema](../schemas/degraded_source_analysis.json). New v1 artifacts:

| Artifact | Purpose |
|---|---|
| DegradedSourceAnalysisRequest | Scope, source/IR request digests, ModuleFacts, optional P3/P4, declared failures, budgets |
| TUEvidenceAvailability | Profiles, stage artifacts, failures, four evidence modes per TU |
| SourceCandidate | Source pthread/atomic/access/control/unknown-synchronization shapes needing further analysis |
| SynchronizationGap | Unknown mutex kinds, RAII lifetimes, wrappers, lock objects/paths, budgets |
| DegradedSourceAnalysisReport | Candidate degradation, formal-assessment adaptation, exact denominators, caches, diagnostics, exits |
| DegradedValidationSuite/Truth/Report | Independent four-language truth and comparison metrics |

AST extraction is not an ad hoc BC-failure fallback. Every planned TU gets an independent source work item first. Later IR/analysis failure never deletes published SourceSemanticFacts digests/content identities.

## 3. Four modes

| Mode | AST | IR/P1 | Allowed conclusions |
|---|---|---|---|
| ast-ir | Trusted | Available | Existing formal P1–P4 analysis, with A2 gap checks |
| ir-only | Unavailable | Available | Existing IR-only behavior without inheriting failed/mismatched source identities |
| ast-only | Trusted | Unavailable | SourceCandidate, unknown/frontier, missing evidence only |
| failed | Untrusted | Unavailable | Failure reasons, no source candidates |

Multiple TU modes make the request mixed. Top-level partial does not automatically contaminate every candidate. A proven-unrelated failed TU does not prevent formal candidate assessment; unproven irrelevance retains dependencies and degrades conservatively.

## 4. AST trust

Complete AST and partial AST truncated only by explicit node/reference budgets may supply source facts. clang-replay-failed, missing headers, syntax/type errors, profile conflicts, fatal diagnostics, and recovery nodes make that TU's AST untrustworthy. Recovery trees cannot establish entity/control/synchronization evidence.

Each SourceCandidate fixes evidence_level=source-only, verdict=unknown, and safety=not-established. It explicitly lists missing memory effects, execution order, byte ranges, thread instances, reads-from, synchronizes-with, and happens-before; AST-only also lacks ir-binding.

Source order/API/type names do not establish SB/RF/SW/HB or P4 findings, severity, discharge, or safety.

## 5. Failure classes

Failures include stage, stability, and bilingual fields:

| failure_class | Examples |
|---|---|
| frontend-invalid | Missing headers, macro failures, syntax/type errors, fatal AST |
| profile-replay-incompatible | GCC-only options incompatible with pinned Clang replay |
| ir-generation-failed | BC emission/parse/verify failure |
| worker-budget | Time, output, memory/resources, or explicit work limits |
| artifact-validation-failed | Schema, digest, identity, dependency, cache corruption |
| analysis-stage-failed | P2/P3/P4 or other worker-stage failures |

Diagnostics are byte-bounded. stdout contains protocol JSON only; worker logs use bounded stderr/diagnostics. Deterministic derived artifacts with valid dependencies may cache; timeout/crash/resource failures are not persistent semantic successes.

## 6. Synchronization gaps and P4 adaptation

SynchronizationGap retains source/IR references, candidate TUs, nodes, relationships, objects, threads, paths, budgets, and dependency digests. Current codes: mutex-kind-unknown, unmodeled-raii-lifetime, unknown-synchronization-wrapper, unresolved-lock-object, unbalanced-or-conditional-lock, synchronization-budget.

Adapters read P4 assessments without modifying original graphs/reports. If a finding/discharged dependency slice intersects AST-only/failed TUs or synchronization gaps, or dependencies cannot resolve, A2 effective_status becomes unknown. Original ID/kind/status remains auditable. Only proven-unrelated gaps can be locally ignored; top-level completeness records all gaps.

Direct same-object ordinary non-robust pthread_mutex_lock/unlock retains the supported P3 model. Lock names alone do not create gaps. A2 corrects the local lock_guard false positive to unknown; full RAII discharge belongs to A4.

## 7. CLI

```bash
python3 -m memory_order_analyzer analyze-degraded-source \
  --request /input/degraded-request.json \
  --artifact-store /artifacts \
  --output /output/degraded-run-001 \
  --source-worker /output/build/memory-order-source-worker \
  --ir-worker /output/build/memory-order-source-worker
```

Output must not exist. Files include request.json/report.json and identity-named source-facts/, llvm-binding-facts/, availability/, source-candidates/, synchronization-gaps/.

- Exit 0: complete, no formal risk; not a safety proof.
- Exit 3: complete with formal risk not overridden by higher-priority incompleteness.
- Exit 2: usable partial/unknown/source-candidate/mixed/budget output, including formal risk alongside planned AST-only candidates.
- Exit 1: invalid request or all evidence unavailable.

Zero candidates/findings, exit 0, and P4 discharge never imply whole-program safety.

## 8. Cache, budgets, determinism

A2 uses derived/degraded-source-analysis-v1 independently of A1/P1–P4 keys. Availability/candidate/report identities bind schema/policy, scope/profile, source/include digests, explicit dependencies, budgets, and relevant toolchain identities. Reject substituted artifacts, dangling dependencies, and damaged entries. Report semantic_digest excludes hit/miss counts for cold/warm equivalence.

Slices support cycles/repeated paths. slice_items limits produce stable frontiers; truncation does not mean no dependencies. Sort lists by machine identity; translations do not affect candidate IDs.

## 9. Limits and other layers

A2 does not implement std::thread, full RAII mutexes, try/timed/recursive/robust mutexes, condition variables/semaphores/rwlocks, general points-to, fences, RMW/CAS release sequences, or general HB/data-race detection. Independent A3/A4/A5/A6 layers provide their documented lifecycle/RAII/provenance/atomic subsets. Their existence does not automatically relax A2's conservative boundaries.
