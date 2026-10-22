# Bounded publication risks and atomic proofs

English | [简体中文](publication-analysis.zh-CN.md)

This guide organizes current protocols, CLIs, budgets, and limits by semantic layer. Products use [unified project analysis](UNIFIED_PROJECT_ANALYSIS.md); layered CLIs support diagnosis. Local proofs/candidates are not whole-program safety. Run examples only inside Docker development containers.

- [P4 single-publication risks](#doc-single-publication-risks)
- [A6 fences, RMW/CAS, and bounded publication](#doc-fence-rmw-publication)

<a id="doc-single-publication-risks"></a>

## P4 single-publication risk analysis

`detect-single-publication-risks` completed implementation on 2026-09-16. P4 adds an independent protocol above P1 ModuleFacts v2, P2 EffectSummary v1, and P3 ThreadContextGraph v1 without changing their artifacts or safety/findings semantics.

### 1. Supported scope

Initial P4 analyzes GCC/Clang C11/C17/C++17/C++20 BC with direct POSIX pthread_create/join entries. Candidates require explicit scope, potentially parallel publisher/consumer ThreadInstances, exact flag/payload ranges, known initial values, one nonrepeated publication write, identifiable success branches, and auditable same-thread order.

Core pattern:

```text
payload write
  -> P4 local must-before
flag release/seq_cst store
  -> bounded unique reads-from
flag acquire/seq_cst successful observation
  -> success-edge control and must-before
payload read/use
```

Results describe discharge or risk only within c-cpp-single-publication-v1. This is neither general data-race detection nor a safety proof.

Initial exclusions include multiple/repeated writers, ABA, consume, fences, RMW/CAS release sequences, std::thread/RAII, complex mutexes, condition variables/semaphores/rwlocks, pools/custom synchronization, general points-to, reclamation, and general data races. Preserve unknown/unsupported/frontier evidence without assuming synchronization or absence.

### 2. Inputs and CLI

Prepare an artifact store and explicit ScopeManifest using the compile-only pipeline, then a P3 ThreadAnalysisRequest. P4 references that request with explicit model/budgets:

```json
{
  "schema_version": 1,
  "kind": "PublicationRiskRequest",
  "analysis_version": "0.1.0",
  "policy_id": "single-publication-risks-v1",
  "thread_request": "thread-request.json",
  "model_id": "c-cpp-single-publication-v1",
  "budgets": {
    "local_steps": 100000,
    "value_candidates": 8,
    "protocol_candidates": 10000,
    "assessments": 10000,
    "scc_iterations": 16,
    "worker_seconds": 60,
    "worker_output_bytes": 16777216,
    "request_seconds": 300,
    "request_output_bytes": 67108864
  }
}
```

Resolve relative paths against the P4 request directory. Output must not exist:

```bash
memory-order-analyzer detect-publication-risks \
  --request publication-request.json \
  --artifact-store out \
  --output publication-result \
  --worker /path/to/moa-worker
```

The workflow uses compile-only BC preparation and analysis without executing programs or implicit llvm-link. Shared directories/headers do not define complete target scope. Compilation databases identify individual TUs; explicit scopes define cross-TU membership/open boundaries. The current product entry consumes BC prepared upstream.

### 3. Four versioned artifacts

| Artifact | Purpose |
|---|---|
| PublicationRiskRequest v1 | Thread request, model, effective budgets |
| PublicationLocalFacts v1 | Per-BC accesses, initializers, observations, gates, return dependencies, local order, evidence |
| SinglePublicationProtocolGraph v1 | Thread/object/observation combinations, bounded reads-from, protocol candidates, assessments |
| PublicationRiskReport v1 | Layered completeness, exact denominators, bilingual diagnostics, verdicts/findings/exits |

Output contains request snapshots, P3 dependencies, publication-local/*.json, graphs/*.json, report.json. Cache namespace derived/single-publication-risks-v1 binds BC/P1/P2/P3, full requests, scope/profile, model, and budgets transitively. Hits never reuse old thread-instance identities.

Schemas reject unknown fields/future versions/dangling references, forged cross-artifact/function AnalysisRefs, duplicate IDs, and inconsistent counts. Raw IR uses SourceRef; analysis-derived dominance gates/order use separate AnalysisRef.

### 4. LLVM and project-owned logic

C++ owns same-version BC parse/verify, DataLayout, constants/ranges, CFG, DominatorTree, LoopInfo, loads/stores/atomic ordering/syncscope, bounded value dependencies, success-edge control regions, and local must-before. Cross-block order requires instruction dominance and nonrepeated accesses; static dominance never guesses dynamic loop order.

Python owns strict contracts, worker isolation, P1–P4 closure, cross-TU direct-return wrappers, thread/object indexes, unique writers/bounded reads-from, rules, caching, completeness, and reports. P2 EffectSummary.order proves neither SB nor HB; P3 reads-from candidates do not directly become SW.

Local transport follows bounded icmp eq/ne, zero/nonzero, Boolean inversion, supported integer casts, phi/select, Clang O0 function-local spills, and definite direct returns. Arithmetic transforms, candidate explosion, indirect/ambiguous wrappers stay unknown.

### 5. SuccessfulObservation

Loop atomic loads may repeat, so raw load nodes retain repeated/may semantics. A separate SuccessfulObservation binds the raw read, P2 invocation, P3 ThreadInstance, predicate, and success edge: if this observation satisfies the predicate and follows that edge into the consumption region.

It proves neither inevitable execution nor a read source. It participates only when success-edge control of payload use, unique wrapper binding, and evidence closure are established.

### 6. Bounded reads-from uniqueness

Upgrade a flag-store/successful-observation candidate to proved only if all hold:

1. Exact initial flag value rejected by the success predicate.
2. Exact publication value accepted by it.
3. One acceptable write in closed scope with single multiplicity.
4. No related RMW/CAS, unknown clobber, open boundary, or repeated publication.
5. Compatible write/read object ranges, widths, and system syncscope.
6. Complete gates, threads, order, and budget evidence.

This belongs only to the current protocol candidate and does not rewrite P3 general RF/MO. Indistinguishable initial/publication values, multiple writers, open scope, or partial relevant evidence degrade.

### 7. Risk classification

| Code/category | Meaning |
|---|---|
| ordinary-conflict / potential-data-race | Potentially parallel overlapping ordinary flag/payload conflict in an identified protocol, without a complete synchronization chain |
| missing-release | Publication store is not release-capable |
| missing-acquire | Successful observation controlling payload is not acquire-capable |
| acquire-too-late | Another acquire is proven after payload use |
| publication-store-too-early | Flag store is proven before payload write |
| all-atomic-relaxed | Atomic flag/payload with relaxed combinations do not establish publication; not an ordinary data-race finding |
| single-publication-discharged | Complete release/acquire or seq_cst discharge within the bounded model |
| protocol-unknown / protocol-unsupported | Unknown prerequisites or synchronization outside initial scope |

Missing payload-before proof is unknown, not proof of early publication. Correct controls record discharged only, never whole-program safety.

### 8. Completeness, budgets, exits

Reports separate input, P1/P2/P3, publication-local, candidate modeling, and risk evaluation, retaining planned/candidate/evaluated/finding/discharged/unknown/unsupported/excluded denominators. Zero-candidate ratios are null, not 100%.

| Exit | Condition |
|---|---|
| 0 | All stages complete, no supported Finding |
| 3 | All stages complete, at least one Finding |
| 2 | Partial/unknown/unsupported makes conclusions incomplete; takes precedence over Findings |
| 1 | Request, structure, worker, or critical-input failure |

safety is always not_established. verdict=no_supported_risk_found means no supported Finding in this bounded model only.

Diagnostics provide detail/detail_en and suggestions suggestion/suggestion_en. Translation does not affect rule identity/exits. Missing debug still retains artifact/function/IR evidence.

### 9. Validation

The semantic matrix uses direct-pthread CASE0–CASE7 plus Clang C11, GCC C17, G++ C++17, Clang++ C++20, three-physical-TU wrappers, no-debug, open-scope, and unsupported std::thread boundaries. Integration inputs compile only, never link or execute.

<a id="doc-fence-rmw-publication"></a>

## A6 fences, RMW/CAS, and bounded publication proofs

model-fence-rmw-publication adds an independent advanced-atomic sidecar over P1–P4, A1–A5, and R1–R3 without modifying old protocols or presenting candidate relations as interthread-order proofs. Inputs are RootDrivenAnalysisPlan, ThreadEntryRootOverlay, R2 atomic handoff, and R3 demand graph. Outputs remain bounded risks, discharge, or unknown, never whole-program safety.

### 1. Versioned artifacts

protocols/advanced-atomic-analysis-protocol.json registers seven v1 documents:

1. FenceRmwPublicationRequest: references, language, scope, budgets, cache policy.
2. AtomicSourceConstructFacts: Clang canonical declarations, actual atomics, types, order arguments, library provenance.
3. AdvancedAtomicFunctionFacts: independent A6 worker reference-closed atomic shards per demanded function/context.
4. AdvancedAtomicLocalFacts: fence/atomicrmw/cmpxchg/atomic-load-store events, paths, contexts, thread instances.
5. BoundedAtomicCommunicationGraph: exact-object bounded RF/MO assignments, release sequences, fence pairs.
6. AdvancedPublicationProtocolOverlay: read-only P4 references plus A6 proofs/counterexamples.
7. FenceRmwPublicationReport: completeness, frontiers, bilingual diagnostics, statistics, cache, exits.

schemas/advanced_atomic.json validates all documents. Semantic digests exclude operational time/path/cache fields for cold/warm equivalence.

### 2. Pipeline

```text
AST canonical atomic facts ─┐
                            ├─ source/IR binding ─┐
P1/R3 demanded LLVM events ┘                     │
A5 object provenance + byte range ───────────────┼─ bounded RF/MO solver
P3 ThreadInstance/MHP ────────────────────────────┤          │
R1/R1.1 root slice + R2 atomic handoff ──────────┘          ▼
                                                   release sequence / fence proof
                                                                │
                                                     P4 read-only overlay + report
```

AST confirms source constructs, declarations, canonical types, and orders. LLVM supplies runtime events, object addresses, control paths, and actual lowering. AST-only retains candidates/missing evidence, never RF/MO/SW/HB/safety.

R3 FunctionSemanticFacts remains unchanged. `moa-worker --advanced-atomic-batch REQUEST.json` reuses lazy materialization/demand transport but outputs separate AdvancedAtomicFunctionFacts; --demand-batch contains no A6-private fields. -O2 direct lowering normalizes directly. -O0 library dispatchers deduplicate only with uniquely aligned canonical operations/orders/functions/locations/SourceIRBinding. Missing A1/A5 object/value binding remains partial; operation/order equivalence is not complete object proof.

### 3. CAS, RMW, outcomes

- atomicrmw retains operation, object, input/result, syncscope, multiplicity, function/context/ThreadInstance; supported operations are xchg/add/sub/and/or/xor.
- cmpxchg separates successful writes from failed read-only events. Success/failure orders remain separate; failure cannot have release semantics.
- Weak CAS with unresolved outcome/guard/loop multiplicity creates a frontier. One successful path cannot establish an entire CAS-loop conclusion.
- RMW must read the immediate predecessor in that object's modification order. Candidate edges, MemorySSA, and EffectSummary.order cannot replace this constraint.

### 4. Language-specific release sequences

| Language | Consecutive events after a release head |
|---|---|
| C11/C17/C++17 | Modifications by the head's thread or RMWs by any thread |
| C++20 | Subsequent RMWs only |

The solver enumerates per-object MO/RF assignments within budgets. Discharge requires every closed valid assignment to support the same publication chain. A complete counterexample yields risk. Incomplete objects, values, outcomes, scopes, or budgets yield unknown/partial.

### 5. Fence combinations

- fence-fence: writes before a release fence, through paired atomic write/read, to reads after an acquire fence.
- fence-atomic: writes before a release fence, followed by an atomic publication write and an acquire atomic read.
- atomic-fence: an atomic read observes a release atomic write, followed by an acquire fence.

Source positions, IR events, and local program order must all be proven. Misplaced fences, atomic_signal_fence, target-specific syncscope, and unmodeled libatomic runtimes create frontiers.

Semantic references: [LLVM LangRef](https://llvm.org/docs/LangRef.html#memory-model-for-concurrent-operations), [LLVM concurrency guide](https://llvm.org/docs/Atomics.html), [C++ fences](https://eel.is/c++draft/atomics.fences), [C++ races/HB](https://eel.is/c++draft/intro.races), [P0982R1 release-sequence changes](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2018/p0982r1.html), and [C11 N1570](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf). These define language/IR semantics and do not replace implementation acceptance.

### 6. CLI, cache, exits

```bash
memory-order-analyzer model-fence-rmw-publication \
  --request request.json \
  --artifact-store artifacts \
  --output output
```

No configure/build/link, program execution, network, or SSH occurs. Verify each input against request-declared SHA-256. Cache keys bind protocols, contents, language/profile/target/DataLayout, scope, policy, and budgets. Cache only complete schema/semantically valid artifacts.

Exits: 0 complete without bounded risk; 3 risk; 2 partial/unknown/frontier; 1 request/input/tool failure. Zero still does not mean whole-program safety.

### 7. Explicit limits

Initial A6 excludes consume, general seq_cst total order, general multiple writers, CAS loops, ABA, reclamation, arbitrary lock-free algorithms, general model checking/HB/data-race analysis. GenMC, herdtools7, and ARM DevKit are optional external comparisons, not core dependencies or correctness oracles.
