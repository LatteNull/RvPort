# Execution roots and demand-driven analysis

English | [简体中文](demand-analysis.zh-CN.md)

This guide organizes current protocols, CLIs, budgets, and limits by semantic layer. Products use [unified project analysis](UNIFIED_PROJECT_ANALYSIS.md); layered CLIs support development/diagnosis. Candidates and local proofs do not establish whole-program safety. Run examples only in Docker development containers.

- [ExecutionRoot-driven architecture](#doc-execution-root-driven-analysis)
- [R2 concurrent-access candidate graph](#doc-concurrent-access-candidate-graph)
- [R3 demand-driven function analysis](#doc-demand-driven-function-analysis)

<a id="doc-execution-root-driven-analysis"></a>

## ExecutionRoot-driven architecture

### 1. Goals and boundaries

R1 changes entry selection from scanning all scope load/store operations and inferring threads afterward to a global lightweight index plus ExecutionRoot-driven deep analysis. It deletes no P1–P4/A1–A5 facts/reports and changes no risk rules. It discovers creation sites/roots, builds bounded reachability along proven direct-call edges, and generates controlled P2/P3 root requests.

R1 fixes safety=not_evaluated and findings=null. Zero candidates means none discovered in explicit scope, not no threads/concurrency or safety. The separate expand-thread-entry-discovery sidecar extends recognition and overlays roots read-only. R2 candidate graphs, R3 lazy extraction, general data races, fences, RMW/CAS, and general HB are outside R1.

Inputs support GCC/Clang C11/C17/C++17/C++20. Direct C pthread paths do not read CppThreadLocalFacts or depend on C++ AST/types/wrapper profiles. Windows/MSVC/clang-cl are excluded.

### 2. Data flow

```text
Optional compile_commands.json (AST profile only) + external BC bundle + explicit scope
              │
              ├── P1 ModuleFacts v2 ───────────────┐
              ├── A1 AST / SourceIRBinding ────────┤ global lightweight evidence view
              ├── P3 ThreadLocalFacts ─────────────┤
              ├── A3 CppThreadLocalFacts ──────────┤
              └── P2 EffectSummary adoption ───────┘
                                      │
                AST candidates union BC candidates; proofs require exact evidence intersection
                                      │
                         ThreadCreationSiteIndex
                                      │
               explicit entry/main/exported/framework/pthread/std::thread
                                      │
                            ExecutionRootIndex
                                      │
                bounded expansion of exact direct calls and adopted wrappers
                                      │
                         RootDrivenAnalysisPlan
                         ├── P2 root requests
                         ├── P3 root requests
                         └── A3 lifecycle overlays
                                      │
                         RootDrivenAnalysisReport
```

Global indexing lightly reads all declared facts in scope to avoid missing sites before entry discovery. Only root-reachable domains create deep-analysis demands. R1 does not claim P1 already extracts lazily per function.

### 3. Field provenance audit

| R1 need | Existing source | Adoption rule | New worker field? |
|---|---|---|---|
| Physical TU, language, profile | A1 requests, R1 members | Explicit request, separate C/C++ profiles | No |
| Definitions, linkage, local direct calls | P1 ModuleFacts.functions/calls | Exact same-artifact in-scope definitions | No |
| Source pthread_create/callback | A1 SourceSemanticFacts.relations | Pair pthread_create with callback from the same call expression | No |
| Source callsite/entity to LLVM | A1 SourceIRBinding expression/entity bindings | Unique target with resolution=exact | No |
| BC thread callsite, ABI, callback SSA | P3 ThreadLocalFacts.calls | Direct, P3-eligible, unique callback for ir-exact | No |
| std::thread callable/wrapper | A3 CppThreadLocalFacts | Exact callable, successful construct, construct-attempt, exact SourceIRBinding | No |
| Cross-TU direct calls | Exact A1 bindings; P2 adoptions | Exact A1 or unique-definition/odr-body-under-contract adoption | No |
| Existing deep observations | P2 summaries, P3 local/graph | Plan/observed reconciliation only | No |

Existing P1/A1/P2/P3/A3 fields covered R1's needs, so R1 added no LLVM/Clang workers or upstream fields. Later entry discovery adds canonical-type, constructor, thrd_create, and C++ broker facts through independent ThreadEntry* v1 artifacts without rewriting R1.

### 4. Entry-discovery overlay and site alignment

R1 originally covers direct pthread and A3-verified std::thread. The entry-discovery change adds ThreadEntryLocalFacts, ThreadEntrySiteIndex, ThreadEntryRootOverlay, and ThreadEntryDiscoveryReport:

- AST recognizes canonical semantic types/records, selected constructors, declaration origins, and library profiles, not spelling or same-name guesses.
- BC validates C callback SSA or follows SourceIRBinding-aligned C++ wrappers to exact brokers.
- Union candidates for recall; upgrade to dual-exact only after alignment. Keep bounded C ir-exact and C++ dual-source rules separate.
- Default/move/factory-return, deferred/conditional async, unsupported frameworks, and failed evidence retain explicit dispositions/frontiers.
- Overlays reference base roots/plans read-only, deduplicate by adopted-from, and add demands without changing base digests/reports.

See [thread-entry discovery](thread-analysis.md#doc-thread-entry-discovery). Exact entries establish trustworthy starting points, not MHP/SW/HB/safety.

AST and BC independently discover candidates; adoption requires their evidence intersection where specified:

- dual-exact: A1 binds source callsite/callback to the same P3 site/callback, or A3 verifies both AST callable and ABI/IR wrapper.
- ir-exact: P3 proves a direct eligible-ABI call and unique callback SSA, without matching AST.
- source-candidate: AST only; retains entities/control evidence but creates no runtime thread root.
- ambiguous: multiple callbacks/bindings or conflicting AST/IR targets.
- unsupported: indirect calls or unsupported ABI/profile/wrappers.
- failed: relevant evidence failed and cannot form a candidate.

Only dual-exact and supported ir-exact create formal thread ExecutionRoots. Names, similar wrappers, and AST-only callbacks are insufficient. Two sites starting the same callback share thread_context_key but retain separate thread_instance_key values.

### 5. ExecutionRoots and reachability

Roots come from explicit program entries; explicitly enabled unique defined main; explicitly declared exported library entries; exact direct pthread_create callbacks; A3-verified std::thread callables; and explicitly declared framework entries bound to source entities.

Exported/framework roots are never inferred from linkage, names, or types. Reachability uses exact same-artifact P1 direct calls, exact A1 cross-TU bindings, and adopted P2 edges only. Indirect calls, missing targets, open scopes, recursion, and budget truncation create nonempty frontiers without falling back to all-defined roots.

RootDrivenAnalysisPlan.demands identifies function + context + physical TU stably. P2/P3 requests derive per root, with A3 library lifecycle overlays recorded separately. Reconciliation records planned/indexed functions and existing P2 deep/P3 artifact observations. Missing observations are not marked analyzed; later executors consume controlled requests.

### 6. Completeness and budgets

Reports separately measure root planned/complete/ratio; reachable function-context planned/complete-definition/ratio; and candidate_relevant creation candidates/exact counts in root-reachable slices.

Unrelated TU gaps do not contaminate a root's candidate completeness; exact creation sites are always relevant. Open scopes, relevant source-only/ambiguous/unsupported candidates, missing definitions, and exhausted budgets make plans partial with exit 2. Complete plans exit 0. Invalid requests, all evidence unavailable, or orchestration failure exit 1. R1 never uses risk exit 3.

Budgets cover TUs, source/IR/binding candidates, roots, functions, contexts, call edges, wrapper depth, SCC iterations, frontiers, diagnostics, total request time, and output. Limits require bilingual frontiers, never empty truncation followed by complete.

### 7. Protocol, cache, CLI

`protocols/execution-root-analysis-protocol.json` and `schemas/execution_root_analysis.json` define v1 ExecutionRootDiscoveryRequest, ThreadCreationSiteIndex, ExecutionRootIndex, RootDrivenAnalysisPlan, and RootDrivenAnalysisReport.

Read only explicitly referenced artifact_store-relative evidence with matching kind/id/digest. Reject absolute paths, `..` escapes, content drift, mixed profiles, and unsupported kinds. Cache namespace execution-root-driven-analysis-v1 keys requests, policy, and dependency digests; failed/transient results are not cached.

```bash
python3 -m memory_order_analyzer plan-execution-roots \
  --request /input/execution-root-request.json \
  --artifact-store /artifacts \
  --output /output/root-plan \
  --source-worker /output/build/memory-order-source-worker \
  --ir-worker /output/build/moa-worker
```

R1 reuses existing evidence. Worker arguments reserve a stable CLI for controlled future execution, without implicit recompilation or old-artifact changes. Output must be fresh:

```text
request.json
thread-creation-sites/index.json
execution-roots/index.json
plans/<semantic-digest>.json
effects/requests/<request-id>.json
threads/requests/<request-id>.json
report.json
```

### 8. Other layers

- Independent ThreadEntry* v1 overlays extend four-language entry facts/type normalization and composition without altering R1 bases.
- R2 builds ConcurrentAccessCandidateGraph on RootDrivenAnalysisPlan + ThreadEntryRootOverlay demand slices, not general data-race/HB.
- R3 makes P1/P2/P3 local extraction genuinely lazy per function/context, constrained by R1 plans.
- A6 adds fences/RMW/CAS and bounded release sequences independently.

R2/R3 require their own authorized OpenSpec changes; R1 cannot silently change P4 risk semantics.

<a id="doc-concurrent-access-candidate-graph"></a>

## R2 concurrent-access candidate graph

### 1. Purpose and architecture

R2 projects R1/R1.1 root demands, P2 effects, P3/A3 lifecycles, A4 mutex proofs, and A5 provenance into one dynamic-access space to form auditable concurrent-access candidates.

```text
RootDrivenAnalysisPlan + ThreadEntryRootOverlay
                    │ demanded root/context/function/TU
                    ▼
      ExecutionInstanceBindingOverlay
      ├─ ExecutionRoot
      ├─ ThreadContext（reusable callback）
      ├─ ThreadInstance（dynamic instance per creation site）
      └─ MHP: parallel-possible / not-parallel / unknown
                    │
EffectSummary + ThreadContextGraph + BoundedObjectProvenanceGraph
                    ▼
       ConcurrentAccessProjectionFacts
                    │ AccessInstance
                    ▼
      bounded object buckets + overlap/MHP pairing
                    │
CppRaiiSynchronizationGraph ──► AccessProtectionOverlay
                    │
                    ▼
       ConcurrentAccessCandidateGraph
                    ▼
       ConcurrentAccessCandidateReport
```

Only demanded slices are instantiated; there is no fallback to all-BC load/store scanning. AST/BC retain upstream candidates separately. R2 consumes versioned, content-addressed facts after profile/lineage validation.

### 2. Upstream field audit

| Upstream | Reused | R2 supplement | Forbidden inference |
|---|---|---|---|
| R1 plan | Demanded roots/contexts/functions/TUs and reachability | Base/overlay denominators | No observed-but-not-demanded/all-defined expansion |
| R1.1 overlay | Adopted roots, physical sites, models, callables, cardinality, conditional frontiers | Scope-wide instance binding | No name/type/broker-only adoption |
| P2 summaries | Effects, invocations, guards, ranges, atomic/order | Dynamic AccessInstance | EffectSummary.order is not SW/HB |
| P3 graph | pthread instances, create/join, same-root MHP | Multiroot families and unified MHP disposition | Missing relation is not not-parallel; RF candidate is not synchronization |
| A3 lifecycle | std::thread callbacks/objects/moves/joins/detaches | R1 root/site instance alignment | No guessed join/wait for incomplete jthread/async |
| A4 | Exact mutex/owner/held-region/bounded proofs | Access protection | Names, lexical scope, or a lock somewhere do not protect accesses |
| A5 | must/may/unknown, storage/path/range/union/lifetime | Overlap, buckets, pair evidence | Fields/string keys/AST-only paths do not prove runtime alias/noalias |

R2 changes no upstream schemas, caches, or reports. Without additional LLVM local facts, ConcurrentAccessProjectionFacts v1 adapts existing evidence without C++ worker changes.

### 3. Protocol and identities

`protocols/concurrent-access-candidate-protocol.json` and `schemas/concurrent_access_candidate.json` use policy/cache namespace concurrent-access-candidate-graph-v1. Six v1 artifacts:

- ConcurrentAccessCandidateRequest: scope, target, ABI, DataLayout, TU profiles, source/BC/binding lineage, and each upstream kind/id/digest/schema/producer/path.
- ConcurrentAccessProjectionFacts: demanded dynamic accesses and observed-but-not-demanded audit counts.
- ExecutionInstanceBindingOverlay: separate roots, contexts, instances, invocations, MHP dispositions.
- AccessProtectionOverlay: concrete pairs bound to closed A4 regions/exact mutex proofs.
- ConcurrentAccessCandidateGraph: candidates, exclusions, atomic handoffs, frontiers, denominators.
- ConcurrentAccessCandidateReport: bilingual diagnostics, four-language counts, exits, fixed non-safety fields.

AccessInstance identity includes scope/profile, root, context, invocation, source/effect evidence, dynamic ThreadInstance, operation, atomicity, guards, object candidates, half-open byte ranges, and cardinality. Two creation sites using one callback produce two instances. Repeated AST/IR/P2/P3 observations of one dynamic access merge evidence. Contradictory exact object/range evidence yields source-ir-access-conflict rather than forced merging.

### 4. Roots, instances, MHP

Deduplicate base/overlay roots only with matching physical site, API model, and callback identity, recording adopted_from. Contexts may be shared; instances retain parent, create site, guard, model, and cardinality.

- Prefer P3 pthread/A3 std::thread lifecycle instances and MHP proofs.
- Exact R1.1 pthread_create/thrd_create/std::thread/jthread/explicit launch::async can form bounded parallel-possible intervals when a unique parent execution instance is known.
- Deferred is already excluded by R1.1; default/combined async policies create conditional frontiers, not formal roots.
- Single instances do not run parallel with themselves; merged/repeated instances retain self-concurrency.
- Different roots without lifecycle relations remain unknown, never default not-parallel.

### 5. Objects, ranges, candidates

A5 domains retain storage instances, subobject paths, union groups, lifetimes, address spaces, guards, and half-open ranges. Comparison yields must-overlap, may-overlap, must-disjoint, or unknown. Same-group union members are not disjoint merely due to different fields; same-name fields on distinct storage instances remain distinct.

Pairing uses bounded reverse buckets by storage/address space. Unknown objects create aggregate frontiers, not a global Cartesian product. Formal candidates require parallel-possible MHP, must/may overlap, and at least one write/RMW/CAS. same-single-instance, proven-not-parallel, read/read, and must-disjoint produce explicit exclusions. Pair IDs are side-independent; multiple buckets merge provenance/guards/evidence.

### 6. Protection and atomics

protected-within-bounded-model requires both concrete accesses/dynamic instances, A4 owners, successful acquire/release or RAII destruction, closed regions, the same exact ordinary non-robust/nonrecursive mutex, thread bindings, guards, and complete dependencies. It applies only to that pair, not a function or program.

Ordinary/atomic, atomic/atomic, RMW, and CAS pairs remain. Atomic pairs enter atomic_handoff. RMW/CAS/failure-order/release-sequence/fence need A6 and yield advanced-atomic-semantics-unsupported frontiers in R2. Atomicity, P2 order, and P3 RF candidates are not converted to SW/HB.

### 7. Completeness, budgets, caching

Separate planned/completed/partial/failed denominators cover roots, contexts, TUs, effects, accesses, instances, MHP, object binding, buckets, pairs, and protection queries. Open scope, AST-only/IR-only, missing effects, source/IR conflicts, unknown objects/MHP/synchronization, profile/ABI/lineage conflicts, and exhausted budgets create nonempty frontiers.

Budgets cover TUs, roots, contexts, effects, accesses, instances, object candidates, buckets, alias comparisons, MHP queries, candidates/exclusions/protection, frontiers, recursion/SCC, diagnostics, worker/request time, and bytes. Insufficient output budget preserves mandatory report envelopes and returns partial, never safety.

Independent cache envelopes bind namespace, stage, full key, and artifact. Keys include requests, budgets, all dependencies. Hits revalidate envelope/schema/semantic digest/current input closure. Partial, failed, timeout, and damaged entries are not successful hits. Semantic digests exclude hit/miss observations, preserving cold/warm equivalence.

### 8. CLI and output

```bash
python3 -m memory_order_analyzer.cli build-concurrent-access-candidates \
  --request /path/to/request.json \
  --artifact-store /path/to/artifacts \
  --output /path/to/new-output
```

Read only explicit relative references; no latest-artifact search, configure/build/link, program execution, network, or SSH. Reject existing output directories. Outputs: request.json, projection/<semantic-digest>.json, execution-instance-binding.json, access-protection.json, candidate-graph.json, report.json.

Exits: 0 complete; 2 partial/unknown/unsupported/frontier; 1 invalid/all unavailable. No P4 risk code 3. Reports fix safety=not_evaluated and findings=null. User detail/limitation/suggestion fields are bilingual.

### 9. Support matrix

| Area | Initial support |
|---|---|
| Compiler/platform | GCC/Clang, Linux-style ABI; no Windows/MSVC/clang-cl |
| Languages | Separate C11/C17/C++17/C++20 profiles, fixtures, truth denominators |
| Entries | pthread, C11 thrd_create, std::thread/jthread, explicit async |
| Lifecycles | Proven P3/A3 relationships; deferred excluded; no guessed future wait/jthread auto-join |
| Objects | A5 bounded stack/global/argument/receiver/subobject/union/pointer propagation |
| Protection | C pthread mutex and bounded exact A4 RAII proofs |
| Excluded | General data-race/HB, pools/executors, custom synchronization, general points-to, fences, RMW/CAS release sequences |

### 10. Interpretation

R2 emits candidates, exclusions, bounded protection, and frontiers only. Exit 0, zero candidates/frontiers, atomic accesses, bounded protection, exact truth matches, and 90% coverage prove neither no data races nor HB closure or safety. Send candidates to explicitly versioned P4/A6 or future risk consumers; retain unsupported/frontiers as abstentions.

<a id="doc-demand-driven-function-analysis"></a>

## R3 demand-driven function analysis

`add-demand-driven-function-analysis` implements an independent R3 v1 sidecar. It is explicit opt-in, retains the eager path, and emits no safety conclusions.

### 1. Architecture

```text
RootDrivenAnalysisPlan + ThreadEntryRootOverlay
                    │ function/context/root demand
                    ▼
        AnalysisDemandGraph（bounded monotonic worklist）
                    │ exact direct-call / verified callback
                    ▼
LLVMModuleIndexFacts ── LLVM 21 lazy bitcode module
  （symbol/linkage/ABI/target/DataLayout only; zero body materialization）
                    │ GlobalValue::materialize(demanded function)
                    ▼
 FunctionSemanticFacts / FunctionEffectFacts / FunctionThreadFacts
                    │ completed shard cache + read-only adapters
                    ▼
       P2 effect view / P3 thread view / R2 input view
```

Global indexing reads module identity, declarations/definitions, linkage, visibility, COMDAT, target, DataLayout, and required source bindings only. It traverses no basic blocks/instructions and builds no DT/AA/MemorySSA/PDT/LoopInfo. Deep extraction begins only when demands are scheduled. Unreachable functions may appear in indexes but never as function shards/materialized instructions.

### 2. Protocol and artifacts

`protocols/demand-driven-analysis-protocol.json` and `schemas/demand_driven_analysis.json` define v1:

- DemandDrivenAnalysisRequest: explicit scope, R1/R1.1 references, TU profiles, layers, budgets.
- LLVMModuleIndexFacts: lightweight whole-artifact index with counts proving zero body/instruction materialization.
- FunctionSemanticFacts/FunctionEffectFacts/FunctionThreadFacts: reference-closed shards per function/context/layer.
- AnalysisDemandGraph: seeds, call edges, consumers, states, recursion/budgets, frontiers.
- WorkerExecutionManifest: batches/attempts, parse/materialization, CPU/wall/RSS/bytes, failure isolation.
- DemandDrivenAnalysisReport: root/reachable/candidate-relevant completeness, cache/resources.

Partial shards cannot masquerade as ModuleFacts, LocalAnalysisFacts, ThreadLocalFacts, or EffectSummary. Read-only adapters emit R3EffectShardView, R3EffectSummaryInputView, R3ThreadShardView, and R3ConcurrentAccessInputView. P2-compatible summaries exist only in memory and retain R3 kinds; missing shards propagate frontiers.

### 3. Explicit CLI

```bash
python3 -m memory_order_analyzer.cli analyze-demanded-functions \
  --request /input/r3-request.json \
  --artifact-store /input/artifact-store \
  --output /output/r3-run \
  --worker /opt/memory-order-analyzer/bin/moa-worker
```

Existing BC artifacts, R1 plans, and R1.1 overlays must pass digest/schema/producer validation. No configure/build/link, program execution, network, or SSH. Output must be new. Exit 0 means shards complete for the requested denominator; 2 partial/unknown/frontier; 1 request/infrastructure failure. All retain safety=not_evaluated and findings=null.

### 4. Demands, identity, cross-TU expansion

Seeds come only from verified R1/R1.1 main, explicit entries, pthread/thrd, std::thread/jthread, and explicit async roots. Function IDs remain artifact + symbol; argument/block/instruction IDs retain raw IR order. Shared identity helpers keep eager/R3 identities independent of scheduling, workers, cache hits, and resource timing.

Only exact direct calls or verified callbacks in completed shards expand demands. Cross-TU targets require unique in-scope linkage/ABI/SourceIRBinding. Indirect calls, same-name ambiguity, missing definitions, and default/combined async create frontiers rather than scheduling every definition. Stable nodes/bounded iterations close recursion; overflow yields recursion-budget.

### 5. Batching, caching, budgets

Sort stable artifact/function/context/layer keys and split by functions_per_batch. Parse BC once per batch; LLVM Modules are never shared between workers. Crashes/timeouts/nonzero exits/invalid JSON/parse/materialize/analysis failures affect only their demand slices; other batches continue.

Keys include whole-BC digest, schema/extractor/policy, profile, target, DataLayout, function/context/layer, and semantic budgets. Atomically cache only completed reference-closed shards; never partial/failed/timeout/crash. Whole-BC digest is the initial conservative invalidation boundary. Cold/warm scheduling/hit/resource fields may differ; semantic digests must match.

Budgets cover TUs, roots, demands, contexts, batches, workers, body instructions, LLVM queries, SCC/recursion, frontiers, diagnostics, CPU/wall, RSS, and bytes. No silent truncation: exhausted budgets identify artifact/function/context/layer/attempt and degrade to partial/frontier.

### 6. Support boundaries

- GCC/Clang input profiles; actual BC reader/worker pinned to LLVM 21. No Windows/MSVC/clang-cl.
- Independent C11/C17/C++17/C++20 profiles. C loads no C++ AST/library models.
- AST remains a separate TU-level layer; R3 does not promise function-lazy Clang AST parsing.
- No A6 fence/RMW/CAS release sequences, general pointers/data-race/HB, risk-rule changes, persistent LLVM daemon, or B1/B2 implementation.

Complete means shards close within explicit demands/supported boundaries only. Zero frontiers/candidates, cold/warm equivalence, and reduced materialization do not prove thread safety, no data races, or whole-program safety.

### 7. Repeatable quality entry

```bash
python3 -m memory_order_analyzer.quality --output /output/r3-quality --integration
openspec validate add-demand-driven-function-analysis --type change --strict --no-interactive
```

Unit coverage includes all project-owned Python/C++ executable code, including unloaded source. Overall, per-language, and affected-module line/branch coverage must each reach at least 90%.
