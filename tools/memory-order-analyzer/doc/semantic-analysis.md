# Semantic facts and object evidence

English | [简体中文](semantic-analysis.zh-CN.md)

This guide organizes current protocols, CLIs, budgets, and limitations by semantic layer. Products call [unified project analysis](UNIFIED_PROJECT_ANALYSIS.md); layered CLIs support development and diagnosis. Candidates and local proofs are never whole-program safety conclusions. Run examples only inside the Docker development container.

- [ModuleFacts / RunReport v2](#doc-semantic-facts)
- [P2 bounded cross-TU effect summaries](#doc-effect-summaries)
- [AST/IR cross-TU evidence](#doc-ast-cross-tu-evidence)
- [A5 bounded object and pointer provenance](#doc-bounded-object-provenance)

<a id="doc-semantic-facts"></a>

## ModuleFacts / RunReport v2: raw semantic facts

`enrich-ir-semantic-facts` implements P1 with LLVM 21.1.8. Producing BC requires preprocessing, semantic checking, and IR compilation, without linking or running target programs. This stage does not judge memory-order defects.

### Versions and responsibilities

| Object | Version | Behavior |
|---|---|---|
| ModuleFacts | 2 | Value tables, conditional edges, call interfaces, memory ranges, initialization, extraction completeness |
| RunReport | 2 | Required fact_extraction and artifact_migrations; existing meanings retained |
| BuildSnapshot / TUManifest / BCArtifact / ScopeManifest / ScopeIndex | 1 | Existing contracts retained; extraction identity in toolchain metadata |

[protocols/extractor-protocol.json](../protocols/extractor-protocol.json) is the protocol/policy source: extractor=0.2.0, facts=2, report=2. CMake generates a C++ metadata header; Python reads the same file. Worker `--protocol` emits machine JSON, while `--version` still reports LLVM. Doctor and every read verify the full identity, not LLVM alone.

New consumers reject ModuleFacts/RunReport v1 and future versions. The old RunReport forbids extra top-level fields, so fact_extraction is not a compatible v1 extension. Do not fabricate historical states or upgrade reports in place. See [JSON Schema](../schemas/contracts.json) for fields and [semantic.py](../python/memory_order_analyzer/semantic.py) for reference consistency.

### Value graph and types

C++ [semantic.cpp](../src/semantic.cpp) registers module symbols, arguments, blocks, and instructions, then collects the required operand closure from memory events, arguments/call targets, conditions, returns, and global initializers. It neither exports every LLVM instruction nor solves general data flow.

- `values[]` contains id, kind, type, type_kind, function/block, operands, details, and status; integers add bits and pointers address_space. Types come from LLVM APIs, not `.ll` parsing.
- Argument IDs append `:arg:N` to function IDs; instructions reuse `:bN:iN`. Named symbols retain `:symbol:`. Unnamed symbols use `:unnamed-symbol:` plus LLVM module slots, avoiding empty-name collisions. Artifact/function position isolates same-name local entities.
- Constant IDs hash complete LLVM type/value representations locally to the module. Integers store bits and hexadecimal strings, avoiding JSON-number truncation of 128-bit values. LLVM integers have no source-language signedness.
- `kind` distinguishes argument/instruction/integer/null/undef/poison/zero/aggregate/symbol/expression/unknown. freeze retains its input as an instruction without selecting a runtime value. Zero aggregates use compact zero; an uninitialized declaration differs from integer zero.
- `operands` preserves LLVM order. select stores condition/true/false; cast input/result types identify source/target types. phi `details.incoming` retains value_ref/predecessor and closes cycles by reference. icmp retains predicates; integer operations retain nsw/nuw/exact; extractvalue/insertvalue retain indices.
- `globals.initializer` is state=value + value_ref or state=declaration + null. Aliases do not masquerade as ordinary initialization. Static initial values do not prove C++ dynamic construction ran.

Unsupported floating-point, some vector/target-specific semantics, inttoptr/addrspacecast, and other uninterpreted nodes retain types, raw relationships, unknown reasons, and located diagnostics. Unknowns are never filled with zero; missing fields never imply no effect.

### CFG and calls

Functions retain parameters, return_type, and vararg. Blocks retain successors plus terminator id/opcode/condition_ref/return_ref/status/edges. Terminator edges contain ordinal/target/kind/condition_ref/case_ref. Distinct switch cases with the same target remain separate. ret void has return_ref=null; unreachable retains its own opcode.

Calls retain called_ref, arguments, result_ref (null for void), function_type, calling_convention, and normal/unwind. Direct targets still serve scope resolution. An indirect called_ref does not imply a resolved target. Unnamed targets are not bound by empty-name guessing.

tail retains the LLVM CallInst enum as a numeric string, or none for non-CallInst calls. ABI attributes retain raw LLVM text; nonempty attributes set attribute_status=unknown and emit uninterpreted_abi_attributes. Bundles retain tag/inputs and explicitly mark opaque_call_features. Unsupported terminators retain real successors with unsupported_terminator. Field presence does not claim modeled ABI or exception-handling semantics.

### Memory ranges

Events contain inputs, result_ref, ranges, and range_status. `available` means a range description exists even if its size is unknown; fences use `not_applicable`, opaque effects `unknown`.

Ranges contain role (read/write/read_write), address_ref, address_space, alignment (null when unknown), and size: `{status: known, bytes: decimal-string}` or `{status: unknown, reason: reason}`. Size comes from module DataLayout store size, not bitwidth/8 or guessed target layout. Structure padding, access-type size, and field offsets are separate.

GEP retains source_type, original base/index operands, and inbounds/nuw/nusw. Known offsets have bits/hex/signed_decimal calculated with the address space's index width. Dynamic GEP or missing layout is unknown. Known/negative offsets do not prove bounds, object validity, aliasing, or legal access. The older bounded address view does not strip pointer conversions, avoiding false cross-address-space object identity.

Loads reference results; store/RMW use inputs.value; CAS uses inputs.compare/new and result_ref. extractvalue indices track old values/success bits and branches, preserving success/failure order, weak, volatile, and syncscope. memcpy/memmove separately record destination writes and source reads with length references and independent address spaces/alignments; memset adds fill. Zero length is known 0; dynamic length remains unknown.

### Budgets and completeness

Policy v1 limits value nodes to 100,000, operand references to 500,000, constant nesting to 64, and worker JSON to 16,777,216 bytes, alongside process time limits. SSA-chain length is not constant nesting. Excessive constant depth leaves a referencable constant_depth leaf. Node/reference/output overflow returns extraction_budget_exceeded and publishes no successful TU facts. Time failures remain timed_out.

ModuleFacts.extraction includes status, roots (unique required roots), nodes, references (value-table operand edges), unknown (diagnostic count), and diagnostics (id/reason). Unknown is not a count of unknown value nodes: dynamic ranges and uninterpreted ABI also contribute. Nonempty diagnostics mean partial. No required roots may be complete, but this is not a safety scan.

RunReport.fact_extraction is independent of parse/verify and source_mapping, with planned/complete/partial/failed, complete_ratio, and diagnostics. Use the full planned denominator, null for zero, and doctor=not_run. Usable partial facts exit 2; all unusable exits 1; no relevant gap exits 0. Missing debug reduces location quality without blocking the value graph. P1 always retains semantic_analysis=not_run, safety=not_evaluated, findings=null, and points_to/effect_propagation/callsite_specialization/threads/memory_model=false. P2–P4 use separate artifacts without changing these meanings. See [P4 boundaries](publication-analysis.md#doc-single-publication-risks).

### Cache migration and use

Use existing collect/import-bc/index/link/doctor commands from [development](development.md), a fresh output directory, and rebuilt worker. `python3 -m memory_order_analyzer --help` shows current arguments. Development and production-container integration are separate changes.

1. collect keys include context/inputs/profile/SDK/full extraction identity. Old generations miss naturally; current caches still rediscover dependencies and check identity.
2. import-bc without a manifest keys by BC hash/current protocol. Provenance stays unknown; ancestry is not guessed.
3. Old manifests are hash-checked, then rekeyed with old key + BC hash + current protocol, preserving context/profile/inputs/provenance and old key/lineage. Reimporting current manifests retains keys without duplicate ancestors.
4. RunReport.artifact_migrations records from/to. Users explicitly rebuild ScopeManifest.members; scope is not changed automatically. index/link always validate v2 structures/references, compatible configurations, and ancestry overlap. Linked keys include scope/protocol, and linked BC is reread as v2.
5. Retain old BC, facts, reports, and scopes; no lossy JSON migration or historical overwrites.

Coverage is not detection accuracy. Call-site bindings, stored-value propagation, and effect summaries belong to the separate P2 layer below.

<a id="doc-effect-summaries"></a>

## P2 bounded cross-TU effect summaries

`add-scoped-effect-summaries` is implemented. P2 adds independently versioned local-evaluation/effect-summary artifacts without changing ModuleFacts v2, RunReport v2, or ScopeIndex v1. It composes definite direct calls in explicit-scope GCC/Clang C/C++ compile-only BC, without implementing thread models, happens-before, risk judgments, or general points-to analysis.

### 1. Layers and responsibilities

P1 retains source-faithful raw IR values, CFG, calls, and atomic events. The P2 C++ worker reads LLVM 21.1.8 BC and builds read-only DominatorTree, BasicAA/AAResults, MemorySSA, local-object, and control-flow evidence for bounded local interpretation. Python owns explicit scope, adoption eligibility, call contexts, cross-TU scheduling, instance rebinding, caches, completeness propagation, and reports.

LLVM provides local semantic queries, not project scope, cross-TU symbol selection, summary contracts, or invocation identity. Those are project-owned. P2 requires no llvm-link, native linking, program execution, SSH, or DevKit.

New artifacts use schema v1, `analysis_version=0.1.0`, and `policy_id=scoped-effects-v1`:

- `LocalAnalysisFacts`: exact linkage/ABI, raw P2 IR nodes, local objects, and LLVM evidence. Its partial status means supplementary facts, not failed effect evaluation.
- `LocalEvaluationRequest` / `LocalEvaluationResult`: candidate values, call bindings, budgets, local effects, and unexpanded frontiers for one function context.
- `EffectSummary`: reusable parameterized summaries with independent invocation/allocation identities.
- `EffectAnalysisRequest` / `EffectAnalysisReport`: requests, layered states, planned counts, dependencies, and diagnostics.

### 2. Entry point

Complete P1 collect/index and create an explicit ScopeManifest containing members of one target/configuration. Then prepare:

```json
{
  "schema_version": 1,
  "kind": "EffectAnalysisRequest",
  "analysis_version": "0.1.0",
  "policy_id": "scoped-effects-v1",
  "scope": "D:/work/scope.json",
  "mode": "roots",
  "roots": [{"artifact_key": "<64-hex-artifact-key>", "function_id": "<P1-function-id>", "arguments": []}],
  "budgets": {
    "local_steps": 100000,
    "condition_states": 32,
    "value_candidates": 8,
    "contexts_per_function": 32,
    "contexts_per_request": 4096,
    "scc_iterations": 16,
    "effect_items": 10000,
    "worker_seconds": 60,
    "worker_output_bytes": 16777216,
    "request_seconds": 300,
    "request_output_bytes": 67108864
  }
}
```

Run:

```text
python -m memory_order_analyzer summarize \
  --request D:/work/effect-request.json \
  --scope D:/work/scope.json \
  --artifact-store D:/work/artifacts \
  --worker /workspace/build/moa-worker \
  --output D:/work/effect-output
```

`--output` must be new; historical output is never overwritten. Outputs include `request.json`, `report.json`, `local/<artifact>.json`, and `summaries/<digest>.json`. stdout contains report JSON only; logs go to stderr. Exit 0 means all root contexts complete, 2 partial with unknown/frontier retained, and 1 request/analysis failure. All retain safety=not_evaluated and findings=null.

Worker `--analysis-protocol`, `--local-batch`, and `--evaluate-batch` serve Python protocol negotiation/batching. Do not bypass full input/dependency validation by treating them as direct user APIs.

### 3. Support boundaries

| Area | Supported | Conservative limits |
|---|---|---|
| Inputs | GCC/Clang C11/C17/C++17/C++20 compile-only pipelines; pinned BC reader | No MSVC/clang-cl, source-program execution, or final linking |
| ABI | C calling convention, fixed integer/pointer arguments, void/integer/pointer returns, native noundef/nounwind/noreturn | varargs, floating/aggregate ABI, byval/sret/inalloca/preallocated, musttail, bundles, unknown attributes remain unsupported/unknown |
| Adoption | Unique ABI-compatible non-interposable exact definitions in scope; bounded closed-scope linkonce_odr + COMDAT any + identical normalized bodies | No arbitrary selection for weak/weak_odr, ordinary linkonce, ifunc, conflicting copies, open boundaries, indirect calls |
| Objects | Defined internal/private or proven non-interposable dso_local globals, parameters, single-instance alloca, constant GEP byte offsets | TLS, mergeable unnamed_addr, complex heap, inttoptr/addrspacecast, dynamic offsets, unbound extern remain unknown |
| Scalars/control | Exact-width LLVM integer operations, casts/comparisons, phi/select, br/switch, disjunctive guards, bounded path/candidate merges | No guessed constants/exclusivity for poison/undef/freeze, overflow flags, undecidable paths, or exhausted budgets |
| Local memory | Exact-range strong updates/load forwarding for initialized, non-escaping, ordinary nonvolatile single-instance stack slots | Uninitialized merges, partial overlaps, lifetime end, escapes, and possible alias clobbers invalidate; atomic/volatile/shared/global loads do not infer values from initializers/prior writes |
| Effects | read/write/RMW/CAS/fence; address, size, value, ordering/failure ordering, syncscope, guard, may/must-normal-return, multiplicity, raw evidence | Unknown calls/asm/unsupported intrinsics produce explicit unknown effects, never empty summaries |
| Composition | Definite direct calls, actual/formal/return substitution, call-site specialization, invocation/template separation, dependency closure | Recursion/context/instance/SCC limits widen to partial unknown; merged instances cannot prove strong updates or must effects |

Body fingerprints normalize SSA names and equivalent local numbering. References to private/internal globals/functions include artifact-qualified identity so same-name statics in different TUs cannot appear ODR-equivalent. Bounded ODR adoption is an analysis contract, not a recreation of final linker selection.

### 4. Values, objects, and instances

Candidates in the finite domain form a disjunction; guards within a candidate form a conjunction. Internal bottom means no worklist contribution yet and cannot publish as a complete empty set. Unknown absorbs uncertainty. Candidate/guard overflow widens the whole value rather than retaining the first N as exact.

Context identifies reusable function + template arguments + scope + policy + budgets. Invocation identifies one abstract call instance; allocations belong to it. Cache-hit templates still rebind instances per call site. Two sites, two calls with equal arguments, and recursive levels do not share allocation identity. Loop allocations and recursively merged instances have merged/unknown cardinality and cannot prove must-alias/noalias, strong updates, exclusive guards, or must effects.

Returns support parameters, global addresses, and constant offsets from parameters/objects. Returning an expired local allocation emits `expired_local_return`; unrepresentable complex returns stay unknown. Cross-TU field pointers retain caller object/invocation ownership rather than transferring it to the callee.

### 5. Call graph, cache, and completeness

Only explicit adopted edges form the definite call graph; SCC information uses stable ordering. Nonrecursive children first produce template summaries, then explicit dependency/call_binding triggers caller reevaluation before visible child effects are composed. Recursive backedges, insufficient SCC iteration, context limits, worker timeouts, and output limits yield nonempty unknown effects/frontiers. Unconverged empty sets cannot publish as complete.

Local-supplement, template, instance, and SCC keys include scope, profile/ABI adoption, policy, budgets, and local dependency closure. Verify canonical digests; publish through same-directory temporary files, fsync, and non-overwriting publication. Reject damaged, stale, future-version, or same-key/different-content entries. Template-only hits require invocation rebinding before instance publication.

Reports separate input integrity, raw extraction, local/interprocedural analysis, source mapping, member/root/context counts, and frontiers. P1 diagnostics remain in P1 artifacts. P2 can register a resolution only with matching facts hash, original diagnostic ID/reason, and analysis evidence; deleting raw partial states cannot improve provenance.

### 6. Excluded conclusions

P2 identifies reachable local/cross-call effects and remaining unknown work within explicit scope, context, and budgets. It establishes no thread instances, may-happen-in-parallel, reads-from, or happens-before; judges neither data races nor release/acquire correctness; and never infers safety from no known effects. Separate [P3 thread contexts](thread-analysis.md#doc-thread-and-sync-contexts) and [P4 single-publication rules](publication-analysis.md#doc-single-publication-risks) retain independent artifacts and leave P2 semantics unchanged.

<a id="doc-ast-cross-tu-evidence"></a>

## AST/IR cross-TU evidence

`integrate-ast-cross-tu-evidence` completed cross-TU missed-finding corrections and final quality gates on 2026-09-20, synchronized main specs, and was archived. This additive sidecar sits outside P1–P5 without modifying P1 ModuleFacts v2, P2 EffectSummary v1, P3 ThreadContextGraph v1, or P4 report semantics.

### 1. Why AST and BC are both needed

BC remains authoritative for execution semantics, atomic ordering, CFG, local value propagation, and thread models. AST adds declarations, canonical declaration, USR, mangled name, linkage, visibility, TLS, types/ABI, macro spelling/expansion ranges, and pthread callback/handle clues. AST cannot replace LLVM execution-order, reads-from, synchronizes-with, or happens-before proofs.

`compile_commands.json` provides per-TU AST directories/arguments only; the analyzer no longer generates BC from it. External records align exactly through compile-record digest, physical TU, source hash, target/ABI/profile, and source facts. Bundle/explicit ScopeManifest defines target membership; directories and compilation databases do not.

### 2. Versioned contracts

`protocols/source-evidence-protocol.json` and `schemas/source_evidence.json` define v1 artifacts:

| Layer | Artifact | Responsibility |
|---|---|---|
| Compilation identity | `CompilationProfileIdentity` | Compiler family/version, standard, macros, includes, target/ABI, debug/optimization, dependency hashes, path maps, GCC→Clang replay status |
| AST extraction | `SourceSemanticRequest/Facts` | Physical-TU declarations, definitions, ranges, bounded value flow, atomics, direct pthread facts |
| LLVM binding supplement | `LLVMSourceBindingRequest/Facts` | Same-BC linkage/visibility/TLS/COMDAT, definition role, typed ABI; no P1 changes |
| Scope-wide entities | `ProgramEntityIndex` | Conservative external/internal/tentative/common/inline/template/ODR/weak/COMDAT/TLS grouping |
| AST–IR binding | `SourceIRBinding` | Entity/expression candidate sets to artifact-local nodes, cardinality, supporting/opposing evidence |
| Read-only overlay | `CanonicalObjectOverlay` | Exact cross-TU declarations/definitions mapped to one program object while retaining LLVM identities |
| Downstream supplement | `AstAssistedCandidateSlices` | Actual AST reports, overlays, artifacts, and missing dependencies for each P4 candidate |

LLVMSourceBindingFacts is necessary because P1 v2 lacks the complete typed symbol ABI required for AST–IR binding. Directly extending P1 would break frozen semantics.

### 3. Profile and physical TU identity

Profile digests cover original GCC/Clang commands, working directory, source/include hashes, target/ABI, and Clang 21.1.8 replay state. Compiler family, macros, standard, target, ABI, optimization, or debug differences create distinct profiles even for the same path. Physical TU identity combines profile and normalized source path.

LibTooling replays GCC input only when marked compatible. GCC-only options, missing includes, fatal diagnostics, and profile/BC mismatches become partial/failed with frontiers; never silently remove them and claim completeness.

### 4. Entity resolution and binding

- External declarations resolve only with compatible type/ABI/TLS/visibility/profile and one strong definition. A declaration-only TU that never references the object and emits no LLVM declaration is neutral when a unique scope-wide definition is proven. Referenced-but-missing symbols remain unresolved.
- File-static/internal/anonymous-namespace entities remain physical-TU-local; names do not merge them.
- C tentative/common definitions merge only under allowlisted compatibility conditions. A unique strong definition can supersede compatible tentative ones.
- Multiple C++ inline/template definitions need identical definition digests; differences are ODR conflicts.
- Weak/linkonce/COMDAT selection never depends on input order; nonunique selection stays ambiguous.
- One exact cross-TU canonical object may map to multiple artifact-local symbols: declarations plus exactly one distinct definition. Deduplicate repeated `(artifact_key, id, kind)` targets reached through different bindings rather than fabricating extra definitions.
- Modeled pthread/standard-library declaration-only entities become system external boundaries and do not pollute candidate-relevant completeness of user flags/payloads. Unknown externals stay unresolved.

Exact entity binding requires consistent set-level evidence for profile/TU, mangled name, definition role, linkage/visibility/TLS, and typed ABI. Expression binding uses debug locations, macro ranges, owning function/object, and opcode context. Bounded columns/ranges distinguish same-line operations; missing columns or ambiguity degrades. Optimized-away or no-debug expressions stay candidate/unresolved; nearest-line guesses never establish memory-model order.

### 5. CLI, cache, and budgets

Upstream prepares per-TU SourceSemanticRequest and per-artifact LLVMSourceBindingRequest from the same compilation database, BC artifacts, and explicit scope, then creates AstAssistedAnalysisRequest:

```bash
python3 -m memory_order_analyzer.cli index-source-evidence \
  --request ast-request.json \
  --artifact-store out \
  --output source-evidence-run \
  --worker /output/build/memory-order-source-worker
```

Output must be new. Caches live only under the explicit artifact store's `derived/ast-cross-tu-evidence-v1/`, keyed by requests and dependency digests. Damaged/stale/mixed-generation entries are misses. Budgets cover TUs, AST nodes, references, diagnostics, entity groups, binding candidates, dependencies, worker/request time, and bytes. Truncation retains original denominators and emits frontiers.

P2/P3/P4 consume this layer only when explicitly supplied:

```bash
python3 -m memory_order_analyzer.cli detect-publication-risks \
  --request publication-request.json \
  --artifact-store out \
  --output publication-with-source \
  --worker /output/build/moa-worker \
  --source-evidence source-evidence-run
```

Omitting `--source-evidence` retains IR-only behavior. Scope/digest mismatches in source reports, bindings, or overlays reject consumption; no search for “latest artifacts” occurs.

### 6. Completeness and safety boundaries

Reports separately count planned/visited/emitted/failed profile replay, source extraction, LLVM binding facts, entity resolution, entity/expression binding, overlay, and downstream consumption. User diagnostics provide `detail/detail_en` and `suggestion/suggestion_en`.

AST callbacks, ordinary textual ordering, unique symbols, canonical objects, and P3 reads-from candidates alone establish no SB/RF/SW/HB and cannot upgrade unknown to discharged. One bounded exception: Clang records exact source sequenced-before between adjacent expression statements in one CompoundStmt, breaking at declarations/control/loops/returns. If both endpoints uniquely bind actual IR memory effects in the same thread instance, P4 may use it as local must-before evidence. It establishes no RF/SW/HB or safety; EffectSummary.order remains invalid for this purpose.

P4 retains both whole-request and candidate-relevant completeness. Unrelated system-entity/TU gaps do not erase existing candidates. If relevant thread/atomic/payload facts exist but composition yields zero protocols, emit bilingual `publication-candidate-unresolved` with structured missing reasons. P4 safety remains not_established. Zero findings, cache hits, AST/IR agreement, and perfect fixed-corpus matches are not whole-program safety proofs.

This layer itself does not support std::thread/RAII, general points-to, fence/RMW/CAS release sequences, consume, thread pools, custom synchronization, complex mutexes, or automatic CMake target-scope import. Later independent layers cover their own explicitly documented subsets.

<a id="doc-bounded-object-provenance"></a>

## A5 bounded object and pointer provenance

### 1. Goals and exclusions

`extend-bounded-object-provenance` adds an independent A5 sidecar for GCC/Clang C11/C17/C++17/C++20. It identifies possible storage instances/subobjects for supported pointers, serving exact-only A4 mutex and P4 publication adapters. P1 ModuleFacts v2, P2 EffectSummary v1, P3/P4, and A1–A4 contracts/report meanings remain unchanged.

A5 emits no risk, discharged, or safe conclusions. Reports fix safety=not_established and findings=null. Exits are 0 complete, 2 partial, 1 failed. AST-only facts establish no runtime alias/noalias, reads-from, synchronizes-with, or happens-before.

Initial exclusions: heap objects, container-internal aliases, virtual calls, general function pointers, arbitrary pointer arithmetic, general points-to, fence/RMW/CAS, and safety decisions. SVF/PhASAR are not dependencies. Future evaluation must independently pin versions, licenses, LLVM compatibility, performance, and accuracy.

### 2. Protocol and layers

See [protocol manifest](../protocols/bounded-object-provenance-protocol.json) and [schema](../schemas/bounded_object_provenance.json). New v1 artifacts:

- `BoundedObjectProvenanceRequest`: explicit scope/roots, physical-TU profiles, AST/IR requests, all budgets.
- `SourceObjectPathFacts`: Clang source paths, always an independent layer rather than an ad hoc BC-failure script.
- `LLVMObjectProvenanceFacts`: local LLVM object candidates, query evidence, direct-call/return facts.
- `BoundedObjectProvenanceGraph`: AST/IR alignment, finite candidates, direct-call composition, exact-only adapters.
- `BoundedObjectProvenanceReport`: modes, completeness, bilingual diagnostics, cache, exit code; no risk verdicts.

CLI:

```bash
python3 -m memory_order_analyzer analyze-object-provenance \
  --request /input/a5-request.json \
  --artifact-store /cache \
  --output /output/a5-run \
  --source-worker /output/build/memory-order-source-worker \
  --ir-worker /output/build/moa-worker
```

Outputs include `request.json`, `source-path-facts/*.json`, `llvm-provenance-facts/*.json`, `graphs/*.json`, and `report.json`. The output directory belongs to this run; artifact-store is a separate content-addressed cache.

### 3. Object identity and lattice

Runtime identity combines:

1. `StorageInstance`: global/stack/parameter/receiver/external/unknown, physical artifact, function, invocation, allocation, lifetime, address space.
2. `SubobjectPath`: field declaration/index, `.`/`->`, array index, explicit dereference/cast, layout offset/size/alignment, union overlap group.
3. `ByteRange`: provable constant byte ranges under DataLayout.

FieldDecl is a path component, not a runtime instance. The same mutex field in two Box instances stays distinct; deterministic wrappers preserve storage identity. Union members share overlap groups and are not disjoint merely because names differ.

Internal bottom is not serialized. Public states are must (one unopposed candidate), may (finite alternatives or opposed evidence), and unknown (required reason, optionally known candidates; never disguised truncation). Every candidate retains guards, proofs, opposed evidence, and dependency slices. Versioned requests budget candidates, guards, path depth, load hops, AA, MemorySSA, capture, call contexts, and recursion; limits produce frontiers.

### 4. Clang AST source paths

Clang 21.1.8 `--object-path-request` extracts:

- C struct/union/nested/pointer fields, parameters, returns, address/dereference, constant/dynamic array indexes, macro spelling/expansion.
- C++ this, object fields, receivers, member/free-call arguments and returns.
- ASTRecordLayout field indexes, offsets, sizes, alignment.
- Candidate/unknown reasons for bitfields, flexible arrays, incomplete/anonymous records, dynamic indexes, lossy/address-space casts, unsupported expressions.

C and C++ paths are independent. C uses C AST/linkage, globals/structs/unions, and direct pthread semantics without C++ profiles.

### 5. Local LLVM analysis

`--object-provenance-request` combines read-only DataLayout/GetPointerBaseWithConstantOffset, ValueTracking getUnderlyingObjects, DominatorTree/LoopInfo, BasicAA/AAResults MemoryLocation queries, MemorySSA defining/clobber queries, and CaptureTracking.

Globals, alloca, parameters/receivers, phi/select, cast/GEP, and pointer loads record inputs/results, analysis nodes, and budget categories. ptr-int, addrspacecast, null/undef/poison, and unknown origins remain unknown.

Private stack slots/pointer fields permit strong updates only with exact range, unique reaching store, store dominance, no relevant MemorySSA clobber, no escape, valid lifetime, and non-atomic/nonvolatile pointer loads. Multiple stores, MemoryPhi, MayAlias/partial overlap, unknown calls, capture, lifetime end, and load-hop exhaustion cannot become must.

### 6. AST/IR alignment and cross-TU composition

Alignment checks physical TU, profile, source base, DataLayout offset, and candidate cardinality. Source field declarations alone cannot establish identity; AST and IR must jointly identify one exact candidate.

Exact cross-TU composition explicitly consumes the unique A1 ProgramEntityIndex definition and P2 EffectSummary.adoptions adopted direct call, composing actual/formal, return, and C++ receiver bindings. Exact source-path/LLVM-object alignment also requires same-scope SourceIRBinding, a unique artifact target, and consistent offsets. Without these dependencies, even one same-name LLVM function remains only a candidate. Indirect/virtual calls, ABI/profile/target/DataLayout conflicts, out-of-scope definitions, weak/COMDAT conflicts, expired local returns, and context/recursion limits degrade. EffectSummary.order proves neither identity nor sequenced-before/happens-before.

A4/P4 adapters accept only one unopposed must object. may/unknown retains `mutex-provenance-ambiguous` for A4 and `object-provenance-ambiguous` for P4 without changing existing severity, exit codes, or safety semantics.

### 7. Modes, cache, and completeness

Each TU records ast+ir, ir-only, ast-only, or failed. Scope completeness aggregates candidate dependency slices: unrelated TU failures do not contaminate independent candidates, while missing relevant evidence yields partial/unknown. Complete empty candidates, failure-induced emptiness, and no request are distinct. Zero findings never means safe.

Cache namespace is `bounded-object-provenance-v1`. Keys bind layer, request payload, and dependency closure. Reads revalidate schema, semantic digest, and dependencies; reject damaged, stale, failed, timeout, or nondeterministic results. Report semantic digests exclude cold/warm hit counts, so equivalent inputs produce identical cold/warm digests.

### 8. Validation

Targeted unit tests:

```bash
python3 -m pytest -q -p no:cacheprovider tests/unit/test_object_provenance.py
/output/build/moa-unit --gtest_filter=ObjectProvenance.*:SourceFacts.*Object*
```

Real-worker validation across four languages:

```bash
MOA_WORKER=/output/build/moa-worker \
python3 -m pytest -q -p no:cacheprovider tests/integration/test_object_provenance.py
```

Final required gate, with a fresh output directory:

```bash
python3 -m memory_order_analyzer.quality --output /output/quality-a5 --integration
```
