# Threads, lifecycles, and synchronization

English | [简体中文](thread-analysis.zh-CN.md)

This guide organizes current protocols, CLIs, budgets, and limits by semantic layer. Products call [unified project analysis](UNIFIED_PROJECT_ANALYSIS.md); layered CLIs support development and diagnosis. Candidates/local proofs never establish whole-program safety. Run examples only in the Docker development container.

- [P3 thread and synchronization contexts](#doc-thread-and-sync-contexts)
- [C++ std::thread lifecycle](#doc-cpp-thread-lifecycle)
- [C++ RAII synchronization](#doc-cpp-raii-synchronization)
- [Thread-entry discovery and root overlay](#doc-thread-entry-discovery)

<a id="doc-thread-and-sync-contexts"></a>

## P3 thread and synchronization contexts

`model-thread-and-sync-contexts` is implemented, passed final quality revalidation, synchronized main specs, and was archived. P3 adds an independently versioned thread-relationship layer above P1 ModuleFacts v2 and P2 EffectSummary v1, without changing their semantics or emitting risk conclusions.

### 1. Capability boundaries

Initial inputs are GCC/Clang user-space C/C++ with explicit ScopeManifest and analysis roots. Supported direct POSIX calls:

| API | P3 event | Required evidence | Otherwise |
|---|---|---|---|
| `pthread_create` | create-attempt, thread-start | Direct C ABI, 4 arguments, consistent callback metadata, unique callback candidate and in-scope definition | Unknown with bilingual diagnostics |
| `pthread_join` | join-attempt, join-complete | Direct C ABI, 2 arguments, bounded handle provenance uniquely reaching one instance | Attempt and frontier only |
| `pthread_mutex_lock` | may-acquire candidate | Direct C ABI, one argument, ordinary static-zero initialization fingerprint | mutex-state-unknown |
| `pthread_mutex_unlock` | release candidate | Same object as lock, proven local must-before order | mutex-state-unknown |

P3 itself excludes std::thread/RAII (handled by A3/A4 below), try/timed/robust/recursive mutexes, condition variables, semaphores, rwlocks, detach/cancel, thread pools, custom synchronization, and general pointer analysis. Similar names or nearby models do not justify adoption; results stay unknown.

### 2. Independent protocol and artifacts

`protocols/thread-analysis-protocol.json` pins protocol_version=1, analysis_version=0.1.0, policy_id=thread-sync-contexts-v1, model_id=posix-pthread-v1, and llvm_version=21.1.8.

`schemas/threading.json` defines five strict v1 artifacts:

1. `ThreadAnalysisRequest`: scope, explicit roots, model, budgets.
2. `ThreadLocalFacts`: pthread candidates, callback metadata/targets, handle/mutex provenance, normal/unwind/no-return anchor inputs.
3. `ExecutionOrderFacts`: local order proofs from LLVM CFG, DominatorTree, PostDominatorTree, LoopInfo.
4. `ThreadContextGraph`: contexts, instances, lifecycles, bound effects, call anchors, order, MHP, mutex/reads-from candidates.
5. `ThreadAnalysisReport`: layered completeness, explicit denominators, dependencies, frontiers, bilingual diagnostics, exit codes.

Schemas reject unknown fields, future versions, and incorrect kinds. Diagnostics provide detail/detail_en and, when applicable, suggestion/suggestion_en. Machine decisions use stable codes, not translated text.

### 3. Data flow and responsibilities

```text
compile_commands.json + explicit scope
        │
        ├─ P1 compile-only BC + ModuleFacts v2（unchanged）
        ├─ P2 LocalAnalysisFacts / EffectSummary v1（unchanged）
        │
        └─ P3 LLVM worker
             ├─ ThreadLocalFacts v1
             └─ ExecutionOrderFacts v1
                       │
                       ▼
              project-owned ThreadContextGraph
                       │
                       ▼
              ThreadAnalysisReport v1
```

LLVM owns BC reading/validation, raw identity, CFG reachability, dominance/post-dominance, loops, and bounded local value forms. Project code owns cross-TU callback binding, P2 invocation/effect ownership by thread instances, handle tokens, lifecycles, MHP, mutex-state candidates, atomic reads-from candidates, budgets, caching, and completeness.

Callback propagation follows direct function addresses, pointer casts, select, and phi only, with at most 8 candidates. Cross-TU declarations bind only in closed scopes without external boundaries, with unique names and supported non-COMDAT definitions; otherwise unknown remains.

### 4. ThreadContext and ThreadInstance

ThreadContext is a reusable template identified by scope, entry, abstract arguments, model, and budgets, referencing P2 EffectSummary. Identical entries/arguments can share it.

ThreadInstance is an abstract execution instance created under a root by a parent instance and create callsite. Two sites creating the same entry share context but receive distinct instances. Loop/recursive creates form merged instances with nonempty frontiers rather than infinite expansion. Merged represents one or more dynamic threads, never a singleton.

Binding P2 invocations/effects creates ThreadAnchor/ThreadEffect objects retaining SourceRef, P2 identity, and owning ThreadInstance. Calling another function does not reassign caller objects to the wrong thread.

### 5. Execution order and lifecycle

ExecutionOrderFacts is the only source for P3 local-order composition:

- Nonrepeated instructions in one block yield must-before in instruction order.
- One-way CFG reachability without sufficient proof yields may-before.
- Cross-block must-before requires dominance, post-dominance, and nonrepeated endpoints.
- Loop events are repeated; possible cross-iteration reversal forbids must-before.
- CFG events that cannot coexist in one invocation are mutually-exclusive.

P2 EffectSummary.order retains raw P2 meaning and proves neither sequenced-before nor happens-before. Cross-call order composes callsite, function-entry, function-exit, and normal-successor anchors. No-return/missing-normal-exit calls do not connect to post-call successors.

Lifecycle events are root-start, create-attempt, thread-start, thread-exit, join-attempt, and join-complete. Create/join success is guarded. Unchecked returns mean possible success, never unconditional spawn/join proof.

### 6. MHP, mutexes, and atomic candidates

MHP uses canonical undirected ThreadInstance pairs with may_parallel, not_parallel, or unknown. Parent continuation after create and overlapping workers yield may_parallel candidates. A unique handle and successful join produce conditional not_parallel only for parent endpoints with local must-before evidence. MHP proves neither actual scheduling, conflicts, nor defects.

Mutex modeling adopts only worker-generated `zero-static:<sha256>` fingerprints containing target triple, DataLayout, and initializer IR. Dynamic/unknown initialization, clobbered objects, unbalanced lock/unlock, or missing must-before remain unknown. Balanced regions on the same normalized mutex in two threads yield synchronization candidates; seeing a lock somewhere in a function does not protect every effect.

P2 atomic read/write/RMW/CAS/fence bind to ThreadInstance while retaining object, range, value, success/failure order, syncscope, and guard. Same-object cross-thread write/read pairs are reads-from candidates only; different objects are explicitly excluded. Same-object release/acquire, fences, CAS spinning, or unknown release sequences do not directly establish synchronizes-with/happens-before.

### 7. CLI

Example request:

```json
{
  "schema_version": 1,
  "kind": "ThreadAnalysisRequest",
  "analysis_version": "0.1.0",
  "policy_id": "thread-sync-contexts-v1",
  "scope": "scope.json",
  "roots": [{"artifact_key": "<64-hex>", "function_id": "<P1-function-id>", "arguments": []}],
  "model_id": "posix-pthread-v1",
  "budgets": {
    "local_steps": 100000,
    "value_candidates": 8,
    "thread_contexts": 4096,
    "thread_instances": 16384,
    "graph_items": 100000,
    "scc_iterations": 16,
    "worker_seconds": 60,
    "worker_output_bytes": 16777216,
    "request_seconds": 300,
    "request_output_bytes": 67108864
  }
}
```

Run inside the development container:

```bash
python3 -m memory_order_analyzer model-threads \
  --request /input/thread-request.json \
  --artifact-store /input/artifact-store \
  --output /output/thread-run-new \
  --worker /output/build/moa-worker
```

Output must not exist. The command generates P3 local facts in explicit scope, then converts user roots and adopted direct pthread_create callbacks into a P2 mode=roots request. Callback arguments without SourceRef use P2's empty-arguments-as-unbound/unknown rule, never fabricated values. P2 content-addressed caches can be reused without implicitly switching to all-defined. P3 sidecars, graph, and report follow without llvm-link, native linking, or program execution.

Exit 0 means all planned layers complete; 2 means a usable partial graph with unknown/frontier; 1 means request/input/worker/structural-budget failure. All retain safety=not_evaluated and findings=null.

### 8. Budgets, caching, and completeness

Exhausted budgets cannot publish dangling edges or empty results as complete. Valid subgraphs may remain partial with nonempty frontiers. If an explicit root cannot even represent its minimum context/instance/root-start, fail the request. Orchestration rechecks total wall time and output size.

Cache keys bind request, scope, profile, P1/P2 digests, worker protocol, model, and budgets. Context-template and instance identities remain separate. Callee-only summary changes/model upgrades invalidate graph keys. Damaged, future-version, or same-key/different-content entries fail explicitly.

Reports separate input_integrity, effect_analysis, local_thread_analysis, thread_modeling, synchronization_analysis, and source_mapping. Member/root/context counts include planned, complete, partial, failed, not_run, and complete_ratio. Zero denominators are null, never 100%.

### 9. Conclusion boundaries

P3 supplies auditable relationship graphs only. It does not judge data races, publication-order risks, whole-program C/C++ safety, or target-hardware barrier correctness. Missing definite HB is not a proven error; mutex/reads-from candidates do not prove synchronization. [P4 single-publication rules](publication-analysis.md#doc-single-publication-risks) use separate artifacts. P3 retains safety=not_evaluated and findings=null.

<a id="doc-cpp-thread-lifecycle"></a>

## C++ std::thread lifecycle analysis

### 1. Scope

A3 `model-cpp-thread-lifecycle` adds a separate lifecycle overlay over P1–P4, A1, and A2, without modifying ModuleFacts v2, EffectSummary v1, ThreadContextGraph v1, PublicationRiskReport v1, or A2 semantics. C11/C17 direct pthread_create/join remains in P3; C TUs load no C++ AST types/library profiles.

A3 supports verified GCC/Clang C++17/C++20 std::thread construction, move construction/assignment, joinable(), join(), detach(), and destruction, with free-function, lambda, nonvirtual member-function, or uniquely resolved simple-functor callbacks. Conclusions are lifecycle evidence, not mutual-exclusion, SW/HB, risk, or whole-program safety proofs.

### 2. Versioned artifacts

Policy is cpp-thread-lifecycle-v1 and analysis version 0.1.0.

| Artifact | Purpose |
|---|---|
| `CppThreadLifecycleRequest v1` | Scope/roots, TUs, P1/P3/A1 dependencies, library profiles, budgets |
| `CppThreadLibraryProfile v1` | Vendor/version, ABI, target, DataLayout, headers, wrapper digests |
| `CppThreadLocalFacts v1` | Independent callables, object operations, wrapper roles, AST/IR evidence |
| `CppThreadLifecycleGraph v1` | Object states, contexts/instances, transitions, start/join/detach/MHP overlays, gaps |
| `CppThreadLifecycleReport v1` | Completeness, bilingual diagnostics, cache counts; fixed safety=not_evaluated and findings=null |

All enforce schemas, unknown-field/version/reference/order/digest checks. A3 has an independent cache namespace. Protocol/dependency/profile/model/toolchain/budget-category changes alter keys. Timeout/crash/failed results cannot become persistent semantic cache entries.

### 3. Evidence chain and module boundaries

1. A1 identifies source constructions, objects, callables, moves, join/detach/joinable, and implicit destructors. ProgramEntityIndex resolves linkage, ODR/COMDAT, internal entities, and system boundaries.
2. P1 supplies direct wrapper calls, arguments/results, and raw IR nodes. Python A3 uses verified profiles to reduce them to construct-attempt, entry-broker, join-attempt, detach-attempt, and handle-transfer.
3. Bounded SSA provenance traverses alloca/load/store/cast/GEP/phi/select only. Escapes, unknown calls, multiple roots, or exhausted budgets remain candidate/unknown.
4. AST callable/entity/object evidence intersects ABI/IR wrappers to form local facts. Names, type spellings, nearest lines, one mangled symbol, or underlying pthread_create alone cannot establish exactness.
5. The state machine builds reusable ThreadContexts and callsite-specific ThreadInstances. Instances bind construction sites, object/handle lineage, guards, and cardinality; cache hits cannot reuse unrelated instances.
6. The P3 adapter reads the original ThreadContextGraph. Only closed worker-exit → join-complete → parent-successor/not-parallel evidence permits joined. EffectSummary.order, source order, or wrapper presence is insufficient.

Underlying pthread calls in library brokers are model-owned evidence, not additional user pthread instances. Ambiguous ownership retains conflicts/gaps rather than silent deduplication.

### 4. Callables and thread-object states

Callables require a unique compatible in-scope AST definition and consistent IR binding cardinality. Lambdas retain call operators; member functions require bounded receivers; simple functors require one nonvirtual operator(). Unresolved overloads, virtual calls, complex std::bind, general function pointers, missing definitions, escapes, or candidate overflow remain unknown.

States: empty, construction-pending, joinable, joined, detached, moved-from, failed, terminated-path, unknown.

- Construction produces thread-start only with complete callback/object/wrapper/normal-success evidence. Source syntax alone creates no dynamic instance.
- Move construction transfers the same instance/handle lineage and leaves the source moved-from.
- Move assignment over a possibly joinable target becomes terminated-path/unknown rather than assumed success.
- joinable() records queries/guards, not completion order.
- Only successful, closed-proof joins produce join-complete/not-parallel. Exceptions, failure, moved-from, or unknown objects retain gaps.
- Detach ends join ownership but retains may-parallel; it produces no join or HB.
- Destruction of a joinable object may call std::terminate; it is not implicit join/detach.
- Loop/recursive construction uses repeated/merged buckets with frontiers; one join cannot discharge the whole bucket.

AST-only retains source candidates/callables/object operations as partial/unknown, never ThreadInstance, thread-start/exit, join-complete, MHP, RF/SW/HB, risk, or discharged.

### 5. Verified library profiles

The development image pins Clang/LLVM 21.1.8, libstdc++ 13, libc++ 21, x86_64-pc-linux-gnu, Itanium ABI, and 64-bit pointers.

| Standard | Vendor | Version marker | Profile ID | State |
|---|---|---|---|---|
| C++17 | libstdc++ | `__GLIBCXX__=20240904` | `1ba2f7fe…ec448a` | verified |
| C++20 | libstdc++ | `__GLIBCXX__=20240904` | `3988f720…28551` | verified |
| C++20 | libc++ | `_LIBCPP_VERSION=210108` | `dc17dd0b…0b500` | verified |

Profiles retain <thread> header digests, DataLayout, exception/RTTI settings, wrapper symbols/calling conventions/parameter roles/digests, and compile-only LLVM IR provenance. Drift, multiple profiles for one standard, unknown vendor/ABI, or unverified state yields partial/unknown, never approximate names. A3 did not modify the production Dockerfile; container integration is a separate change.

### 6. CLI

```bash
python3 -m memory_order_analyzer model-cpp-thread-lifecycle \
  --request request.json \
  --artifact-store artifacts \
  --output output-a3 \
  --source-worker build/memory-order-source-worker \
  --ir-worker build/moa-worker
```

Consume explicitly referenced artifacts only: no latest-result search, scope expansion, build, or program execution. Output must not exist. --source-worker/--ir-worker preserve the common orchestration interface; composition uses referenced worker artifacts without rerunning upstream stages.

Exit 0 means a complete lifecycle graph for the request, 2 partial/unknown/unsupported, and 1 invalid request, damaged dependencies/profiles, all planned work failed, or runtime error. Zero does not prove thread safety.

### 7. Completeness, budgets, and degradation

Budgets cover TUs, callables, objects, instances, transitions, relationships, recursion, candidates, worker/request time, output, and diagnostic bytes. Limits retain facts, hit/total, and nonempty frontiers with partial status. Gaps enter dependency slices by TU/entity/object/call/thread/path/protocol. Relevant P4 candidates become unknown; proven-unrelated C pthread candidates may proceed, but top-level scope remains incomplete.

Every gap/failure/unknown has a stable code, Chinese detail/suggestion, and English detail_en/suggestion_en. A2 SynchronizationGap still blocks risk judgments for unknown RAII mutexes. Resolved thread lifecycles do not imply resolved mutex lifetimes.

### 8. Explicit exclusions

Initial A3 excludes Windows/MSVC/clang-cl, std::jthread/async, thread pools, executors/custom schedulers, full RAII mutexes, condition variables/semaphores/rwlocks, try/timed/robust/recursive mutexes, general pointer analysis, fences, RMW/CAS release sequences, and general HB/data-race solving. Profile mismatches/unsupported constructs become unknown/frontier, not “no threads/synchronization.”

See [lifecycle validation records](../tests/fixtures/documentation/history.md#doc-cpp-thread-lifecycle-validation). A4 models RAII, A5 extends object provenance, and A6 extends fences/RMW independently.

<a id="doc-cpp-raii-synchronization"></a>

## C++ RAII synchronization

### 1. Boundaries

A4 adds independent CppRaiiSynchronization* v1 sidecars without changing P1 ModuleFacts v2, P2 EffectSummary v1, P3 ThreadContextGraph v1, P4 SinglePublicationProtocolGraph v1, or A1–A3 semantics. Inputs are GCC/Clang; new library semantics cover C++17/C++20. C11/C17 retain separate direct pthread_mutex_lock/unlock paths without C++ AST/profile dependencies.

Initial support covers measured profiles for std::mutex, lock_guard, bounded unique_lock, and small fixed scoped_lock sets. try_lock, timed/recursive/robust mutexes, condition variables, semaphores, rwlocks, general pointers/HB, fences, and RMW/CAS yield partial/unknown with nonempty frontiers.

### 2. Layers and protocol

CppRaiiSynchronizationRequest v1 explicitly lists scope, physical TUs, source/IR facts, P3/A3/A2/optional P4 dependencies, profiles, and per-layer budgets. Resolve dependencies exactly by kind/id/SHA-256. Reject drift, missing/future artifacts, mixed targets/profiles, or existing output directories without searching for substitutes.

CppRaiiLocalFacts v1 retains mutexes, owners, operations, source/IR nodes, and frontiers. Clang records mutex objects/fields, RAII owners, construction, implicit destruction, moves, explicit lock/unlock/owns-lock, and unsupported tags. LLVM derives candidates from actual ModuleFacts call/invoke, arguments, DataLayout, calling convention, normal/exception successors, and SSA provenance, then adopts exact profiles. AST scope alone cannot establish acquire/release/SW/HB.

CppRaiiSynchronizationGraph v1 separates MutexInstance, RaiiOwnerInstance, operations, held-regions, and proof identities. CppRaiiSynchronizationReport v1 references graph/profile, completeness, budgets, cache, and bilingual fields; safety=not_established and findings=null. Translation text is excluded from machine identity.

See [protocol](../protocols/cpp-raii-synchronization-protocol.json) and [schema](../schemas/cpp_raii_synchronization.json).

### 3. Profile/ABI matrix

| Standard | Library | Pinned evidence | State |
|---|---|---|---|
| C++17 | libstdc++ | Clang 21.1.8, `__GLIBCXX__=20240904`, Itanium ABI, x86_64, actual lock/unlock wrappers | verified |
| C++20 | libstdc++ | Same evidence, separate standard identity, related A3 profile | verified |
| C++20 | libc++ | Clang/libc++ 21.1.8, `_LIBCPP_VERSION=210108`, Itanium ABI, x86_64, actual wrappers | verified |
| C++17 | libc++ | Not registered | unsupported/unknown |

Entries are in [cpp-raii-profiles](../cpp-raii-profiles). Adoption compares vendor/version/standard/ABI/target/DataLayout/pointer width/exceptions/RTTI/header digest/wrapper signature/model version/A3 association. Similar vendors or function/mangled names are insufficient. If A3 matches but A4 does not, retain lifecycle evidence and degrade RAII synchronization.

The development container supplies both libstdc++ and libc++21. A4 did not alter the production Dockerfile. Profile probes compile to LLVM IR only, without linking/running programs.

### 4. Owner state machine

States: uninitialized, owns, deferred, moved-from, released, unknown.

- lock_guard enters owns only after successful construction and exact lock wrapper/object/CFG/cleanup evidence; unique paired unlocks on normal/exception exits establish released.
- unique_lock's ordinary successful constructor enters owns; defer_lock enters deferred, then a unique successful lock() enters owns. Explicit unlock() or owning destruction releases. Repeated lock/unlock, adopt/try/release/swap, or unclear owns-lock guards become unknown.
- Move transfers only ownership tokens, preserving mutex identity. Moved-from owners cannot release twice. Owned targets, self-move, or ambiguous sources remain unknown.
- scoped_lock requires complete identities, successful acquisition, and reverse-order release for every mutex. One unknown element prevents a group must-held proof.
- C pthread uses a pthread-direct owner for paired regions, with an empty synchronization_profile_id and no C++ profile adoption.

Throwing constructors, missing cleanup, may-alias objects, dynamic GEP, candidate overflow, or merged states cannot publish must-held regions.

### 5. Bounded proof chain

A complete proof requires the same normalized ordinary non-robust mutex; exact successful acquire; paired release on every relevant normal/exception path; access inside a closed held-region; explicit ThreadInstance; P3/A3 possible-parallel proof; and complete profiles, objects, paths, and candidate dependencies. It references both operations/held-regions, mutexes, threads, and original source/IR nodes.

mutual-exclusion and mutex-sync-candidate describe only this bounded same-mutex model, not general SB/HB closure. They cannot replace atomic RF/MO/release-sequence/fence proofs or use unrelated locks to discharge publication risks. P2 order, P3 RF candidates, A3 join/detach, type/function names, or lexical scope alone never prove synchronization.

A2/P4 composition uses dependency slices. Only a complete A4 proof for the same TU/entity/object/call/thread/path/profile/protocol closes a related gap. AST-only, may, partial, zero candidates, and unrelated proofs retain unknown. The local archived `safe/03_pthread_mutex.cpp` sample discharges only with a complete bounded chain, never as whole-program safety.

### 6. CLI, cache, exits

```bash
python3 -m memory_order_analyzer model-cpp-raii-synchronization \
  --request /input/cpp-raii-request.json \
  --artifact-store /artifacts \
  --source-worker /output/build/memory-order-source-worker \
  --ir-worker /output/build/moa-worker \
  --output /output/a4-run
```

Output must be new and contains request.json, per-TU local-facts/*.json, graphs/*.json, and report.json. Cache namespace cpp-raii-synchronization-v1 keys schema/model, all dependencies, toolchain/profile, budgets, and implementation identity. Failed, timeout, wall-clock partial, and profile mismatch are not persistent semantic hits. Cold/warm semantic digests match; hit/miss counts are excluded.

Exit 0 means a complete request, possibly with zero candidates; 2 partial/unknown/frontier; 1 invalid request/analysis failure. A4 never returns risk code 3. User diagnostics provide detail/detail_en, limitation/limitation_en, and suggestion/suggestion_en, explicitly retaining the bounded-model limitation even for complete proofs.

### 7. Budgets and non-goals

Requests independently limit TUs, source/IR nodes, profiles, mutexes, owners, wrappers, contexts, transitions, held-regions, relationships, recursion, candidates, worker/request time, and output. Limits retain known may facts, limit values, and nonempty frontiers, never empty summaries implying no synchronization.

A4 excludes Windows/MSVC/clang-cl, std::jthread, pools/executors, custom synchronization, the full RAII mutex family, general points-to/data-race, and whole-program safety. A5/A6 independently extend bounded provenance and fence/RMW/CAS. B1 CMake-scope import and B2 container integration remain separate changes.

<a id="doc-thread-entry-discovery"></a>

## Thread-entry discovery and root overlay

`expand-thread-entry-discovery` adds a separate entry-semantic layer before R1's global lightweight index and ExecutionRoot-driven deep analysis. It identifies possible thread-creating sites, callables, and root-admission evidence, not thread safety.

### 1. Layers

1. Clang extracts C API declarations, CXXConstructExpr, canonical records, actual constructors, spelled/canonical types, alias chains, callables, objects, and macro positions.
2. LLVM extracts direct pthread_create/thrd_create callback SSA, handles, results, and success observations. C++ follows SourceIRBinding-bound outer calls through bounded definite wrappers to verified brokers.
3. ThreadEntryLocalFacts v1 retains both AST/IR observations. Candidates are unioned; evidence refines only when physical TU, profile, model, callsite, callback, target, DataLayout, and broker role agree.
4. ThreadEntrySiteIndex v1 separates evidence state, execution semantics, and root disposition so discovery, definite creation, and root eligibility are distinct.
5. ThreadEntryRootOverlay v1 references R1 ExecutionRootIndex/RootDrivenAnalysisPlan read-only, removes duplicate existing roots, and adds callable contexts, create-site origins, and reachable demands without altering R1 artifacts.

### 2. AST semantic types

Recognize standard C++ threads through resolved Clang semantics only:

- Canonical records must be profile-registered std::thread, std::__1::thread, std::jthread, or std::__1::jthread.
- Preserve spelled and canonical types, including aliases such as `using worker_thread = std::thread`.
- Classify constructors as default, callable, move, copy/deleted, factory return, or unknown. Default/move/factory callsites do not themselves create new threads.
- Custom thread types, unregistered boost::thread, Form.submit, enqueue, post, and clone are not adopted by similar names.

std::jthread adds stop-token injection candidates. Selected std::async overloads and bounded enum flow classify async, deferred, default, both, or unknown. AST alone establishes no runtime broker, MHP, synchronization, or HB.

### 3. BC brokers and profiles

[models/thread-entry-models.json](../models/thread-entry-models.json) independently versions entry models. Profiles bind API family, canonical entity, library vendor/version, C++ ABI, target, DataLayout, header SHA-256, exact broker symbol, wrapper role, and full digest.

Current pinned-container registrations:

- libstdc++ `13.3.0-6ubuntu2~24.04.1`: std::jthread/async use the exact `_M_start_thread` broker.
- libc++ `21.1.8`: both use the ABI-tagged exact `__libcpp_thread_create` broker.
- Other vendor/version/ABI/target/DataLayout combinations remain unsupported/partial, without approximate matching.

One broker may serve thread/jthread/async. Mangled symbols or underlying pthread_create alone cannot identify the high-level API. Follow AST callsite → SourceIRBinding → definite wrapper chain, then validate the matching profile. Inlined-away brokers, ambiguity, or exhausted budgets retain source candidates/frontiers.

### 4. Three site dimensions

| Dimension | Values | Meaning |
|---|---|---|
| evidence_status | dual-exact, ir-exact, source-candidate, ir-candidate, ambiguous, unsupported, failed | AST/IR alignment |
| execution_semantics | creates-thread, may-create-thread, does-not-create-thread, unknown | Creation semantics |
| root_disposition | adopted, conditional-frontier, excluded, frontier | Formal-root eligibility |

Direct C pthread_create/thrd_create may be ir-exact with complete ABI, callback SSA, and model evidence. C++ library entries require exact AST+BC evidence; IR-only mangled names are not adopted. Explicit launch::async may be adopted; launch::deferred is excluded; default/combined policies create conditional frontiers.

Duplicate observations at one physical site merge. Different create sites for one callable retain separate sites/dynamic root origins while sharing canonical callable context. Loop/recursive creation retains repeated/merged cardinality.

### 5. Completeness, budgets, caches

Requests limit TUs, source/IR facts, type/alias depth, sites/bindings/callbacks/profiles, wrappers, roots/contexts, SCCs, frontiers, diagnostics, output, and wall time. Limits retain facts and hit/limit with partial status, never an empty set implying no threads. Open scopes, related dependency failures, profile/ABI conflicts, ambiguous callbacks, missing brokers, and conditional async create nonempty frontiers.

Cache namespace thread-entry-discovery-v1 binds full requests, scope/profile, models, budgets, and explicit dependency digests. Publish deterministic complete results only. Damaged, stale, failed, timeout, or wall-clock partial entries cannot be valid hits.

### 6. CLI

```bash
python3 -m memory_order_analyzer.cli discover-thread-entries \
  --request /input/thread-entry-request.json \
  --artifact-store /input/artifact-store \
  --output /output/thread-entry-run \
  --source-worker /output/build/memory-order-source-worker \
  --ir-worker /output/build/moa-worker
```

V1 reads explicitly referenced versioned facts only. It does not discover latest directories, compile, link, execute programs, access the network, or use SSH. Worker arguments retain the common CLI shape; existing explicit facts require no worker launch. Output must not exist.

Exit 0 means discovery complete in request scope; 2 partial/unknown/unsupported/frontier; 1 invalid request or all failed. Reports retain safety=not_evaluated and findings=null. Exact entries and zero candidates are not safety proofs.

### 7. Support boundaries

Supports GCC/Clang C11/C17/C++17/C++20; excludes Windows/MSVC/clang-cl. Built-ins cover direct/bounded-wrapper pthread and C11 threads, plus verified std::thread/jthread/async profiles. Pools, arbitrary executors/custom schedulers, general function pointers/data races, fences, RMW/CAS, and HB solving are outside this layer.
