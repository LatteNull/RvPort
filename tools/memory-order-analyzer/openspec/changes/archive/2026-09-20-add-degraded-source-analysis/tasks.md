## 1. Baseline and protocol compatibility

- [x] 1.1 Freeze current P1–P4/A1 schemas, CLI exit codes, cache identities, fixtures and semantic digests; add regression assertions proving existing requests remain unchanged without degraded mode.
- [x] 1.2 Inventory current collect/source-index/P1–P4 orchestration and failure surfaces, mapping frontend, IR emission, verify, worker, budget and artifact-validation failures to concrete code paths.
- [x] 1.3 Define strict `DegradedSourceAnalysisRequest v1`, `TUEvidenceAvailability v1`, `SourceCandidate v1` and `DegradedSourceAnalysisReport v1` schemas with kind/version/policy/digest/dependency identities and deterministic ordering.
- [x] 1.4 Add schema and reference unit tests for normal inputs, unknown fields, future versions, duplicate identities, dangling/replaced dependencies, mixed profiles, invalid denominators and canonical digest stability.
- [x] 1.5 Decide and document the additive wrapper boundaries used to consume P1–P4/A1 products without modifying their published semantic meaning; lock them with compatibility tests.

## 2. Independent source and IR translation-unit planning

- [x] 2.1 Refactor planning so each explicit-scope TU has independent source and BC/P1 work items sharing one immutable `CompilationProfileIdentity`, source/include digest, physical TU identity and lineage.
- [x] 2.2 Preserve separate planned/completed/failed/budget counts and product references for source, BC, P1, P2, P3 and P4; one successful path must not overwrite another failure.
- [x] 2.3 Implement deterministic failure records for `frontend-invalid`, `profile-replay-incompatible`, `ir-generation-failed`, `worker-budget`, `artifact-validation-failed` and `analysis-stage-failed`, including stage and deterministic/transient classification.
- [x] 2.4 Add bounded, sanitized bilingual diagnostic mapping for compiler/worker failures, ensuring stdout remains protocol JSON and stderr/output cannot exceed configured limits.
- [x] 2.5 Add unit tests for Clang and compatible GCC records, GCC-only extensions, missing generated headers, macro/include failures, syntax/type errors, IR emission/verify failures, P2/P3/P4 failures and time/output/work budgets.
- [x] 2.6 Verify compilation planning never executes shell substitutions, target programs, native linking, CMake configuration, network access or scope expansion.

## 3. Trustworthy AST facts without BC

- [x] 3.1 Extend source extraction/reporting so valid profile-consistent, reference-closed SourceSemanticFacts can be published independently of BC/P1 success with explicit usable/partial/failed state.
- [x] 3.2 Define the fatal/non-fatal diagnostic policy for usable AST-only facts and reject error-recovery nodes from missing declarations, incompatible types, fatal includes or profile conflicts as semantic evidence.
- [x] 3.3 Preserve source product digests when a later IR/downstream worker fails, while recording missing IR and preventing source success from upgrading overall completeness.
- [x] 3.4 Implement C11/C17 extraction coverage for C linkage, tentative/common/static objects, global and struct/union fields, macros, direct pthread calls, `_Atomic`, `<stdatomic.h>` operations and source control relations without C++ matchers.
- [x] 3.5 Maintain independent C++17/C++20 extraction for corresponding pthread/atomic constructs and possible RAII/wrapper observations without assigning RAII synchronization semantics.
- [x] 3.6 Add C++ worker unit tests for valid AST without BC, fatal recovery nodes, C/C++ identity separation, macro atomic control, C struct/union facts, C++ RAII observations, budgets and deterministic ordering; meet affected C++ module line/branch coverage at 90% or above.

## 4. Evidence availability and analysis modes

- [x] 4.1 Implement `TUEvidenceAvailability` construction from explicit products and failures, validating profile/scope/digest identity and never scanning directories for the latest artifact.
- [x] 4.2 Compute per-TU and per-candidate `ast-ir`, `ir-only`, `ast-only` and `failed`, plus request-level mixed state and exact hit/total denominators.
- [x] 4.3 Preserve existing IR-only behavior when AST is unavailable, while ensuring IR-only never inherits source identities or relations from a failed/mismatched profile.
- [x] 4.4 Classify AST-only only when source facts satisfy the trust policy and required IR/downstream evidence is absent; classify wholly untrusted inputs as failed.
- [x] 4.5 Add Python unit tests covering all four modes, mixed requests, zero denominators, unrelated partial TUs, replaced products and mode ordering/digest determinism.

## 5. SourceCandidate generation and proof boundary

- [x] 5.1 Implement `SourceCandidate` generation for supported source-level pthread/atomic shapes, entity/object/control candidates and cross-TU declaration/definition evidence without requiring BC.
- [x] 5.2 Record `evidence_level=source-only`, `verdict=unknown`, `safety=not-established`, assumptions and explicit missing memory effect/order/range/thread/RF/SW/HB evidence for every candidate.
- [x] 5.3 Prohibit SourceCandidate from using P4 finding IDs, severity or discharged state, and prohibit source order/API spelling from generating SB/RF/SW/HB or formal risk.
- [x] 5.4 Support C global/struct/union/macro/`_Atomic` candidates and C++ pthread/atomic/unknown-RAII candidates through language-specific adapters without cross-language type matching.
- [x] 5.5 Add positive and negative unit tests for source candidates, fatal AST rejection, ambiguous entities, missing callbacks, multiple objects, source sequence without IR binding and accidental P4-field promotion.

## 6. Candidate dependency slicing and cache

- [x] 6.1 Build deterministic dependency nodes/edges for TU, source fact, entity, binding, object, call, thread instance, memory effect, synchronization gap, source candidate and publication candidate.
- [x] 6.2 Compute bounded transitive slices and missing-evidence summaries for formal assessments and source candidates; if unrelatedness cannot be proved, conservatively retain the dependency.
- [x] 6.3 Preserve an ast-ir/ir-only formal candidate when a failed or AST-only TU is proven outside its slice, while retaining request-level partial completeness.
- [x] 6.4 Degrade candidates whose flag, payload, callback, wrapper, thread, control or synchronization path depends on an AST-only/failed TU; do not substitute another TU's IR.
- [x] 6.5 Add slice budgets, cycle handling and stable frontier identities with unit tests for cross-TU chains, recursion, duplicate paths, unrelated utilities, truncation and zero candidates.
- [x] 6.6 Implement separate source/availability/candidate/report caches keyed by schema/policy, scope/profile, source/include and dependency digests, budgets and toolchain identity.
- [x] 6.7 Cache only dependency-valid deterministic failures; prevent transient crash/timeout/resource failures from becoming long-lived semantic cache hits and test cold/warm semantic digest equality plus corruption isolation.

## 7. Unknown synchronization and conservative propagation

- [x] 7.1 Define strict `SynchronizationGap` representation with source/IR references, call/object/thread/path candidates, reason, stage, budget and dependency digest.
- [x] 7.2 Generate gaps for unknown mutex kind, unmodeled RAII lifetime, unknown synchronization wrapper, unresolved lock object, unbalanced/conditional lock paths and relevant synchronization budget loss.
- [x] 7.3 Preserve supported direct same-object C/C++ pthread mutex candidates and ensure the new gap path does not replace complete existing lock/unlock evidence.
- [x] 7.4 Slice each gap against candidate threads, objects, calls and paths; only proven-unrelated gaps may be ignored locally, while global completeness retains every gap.
- [x] 7.5 Add unit tests proving a lock-like name alone cannot create synchronization, an unmodeled wrapper cannot prove absence of synchronization, direct C pthread mutex remains supported and unrelated gaps do not erase formal candidates.

## 8. P4 integration, reporting and CLI

- [x] 8.1 Add an explicit P4/degraded adapter that checks AST-only/failed dependencies and SynchronizationGap before emitting potential-data-race, publication-order-risk or discharged assessments.
- [x] 8.2 Make a candidate unknown when a relevant degraded dependency or gap may change thread/object/access/order/synchronization evidence, with structured bilingual missing reasons.
- [x] 8.3 Keep complete candidates evaluable when degraded TUs/gaps are proven unrelated, while preserving top-level partial scope and exact denominators.
- [x] 8.4 Keep SourceCandidate, P4 finding, discharged, unknown, unsupported and excluded products structurally and numerically separate in report validation, rendering and semantic digests.
- [x] 8.5 Implement `analyze-degraded-source --request --artifact-store --output --source-worker --ir-worker` with empty-output enforcement, explicit dependencies, bounded stdout/stderr and no target execution/linking/scope expansion.
- [x] 8.6 Implement and unit-test combined exit semantics: 0 complete/no formal risk, 3 formal risk without higher-priority incompleteness, 2 usable partial/unknown/source candidate/budget/mixed, and 1 invalid or wholly unavailable.
- [x] 8.7 Add stable bilingual mode, failure, available/missing evidence, limitation, source-candidate and suggestion fields whose machine identities and ordering do not depend on translations.
- [x] 8.8 Add negative tests proving source-only evidence never triggers exit 3, zero candidate/finding never means safety, and a formal risk plus an AST-only planned candidate exits 2 while preserving both records.

## 9. C11 and C17 semantic fixtures

- [x] 9.1 Add independent C11 and C17 single-TU and at-least-three-physical-TU fixtures for direct pthread create/join, C linkage, globals/statics, struct/union fields, macros, `_Atomic` and `<stdatomic.h>`.
- [x] 9.2 Add C ast-ir, ir-only, controlled ast-only and failed fixtures, including missing include/generated input, GCC replay incompatibility, IR worker failure, downstream worker failure and budgets.
- [x] 9.3 Add minimal reviewed C pthread mutex safe/risk pairs: supported same-object mutex must not report unsynchronized risk, while equivalent conflict without synchronization remains detectable in the supported model.
- [x] 9.4 Add C cross-TU slicing fixtures showing a failed relevant wrapper degrades its candidate and an unrelated failed TU does not erase a complete candidate.
- [x] 9.5 Assert C fixtures do not load or require C++ standard-library entities, class/template/RAII matchers or C++ truth annotations.

## 10. C++17 and C++20 degradation regressions

- [x] 10.1 Add independent C++17 and C++20 ast-ir, ir-only, controlled ast-only and failed fixtures using direct pthread/atomic constructs and unmodeled RAII observations.
- [x] 10.2 Create a minimal, compiler-valid, manually reviewed equivalent of archived `safe/03_pthread_mutex.cpp`, preserving source provenance/hash notes without making the sibling archive a runtime dependency.
- [x] 10.3 Reproduce the existing false positive, then assert candidate-relevant unknown RAII changes the formal result from risk to unknown/partial without claiming safety or complete mutex support.
- [x] 10.4 Retain a direct pthread unsafe counterpart as a formal risk when no synchronization or relevant gap exists, preventing over-broad abstention.
- [x] 10.5 Inventory archived sample outcomes and classify Windows/MSVC, invalid source, unsupported C++ concurrency and eligible regression cases; exclude non-eligible cases from accuracy denominators with reasons.

## 11. Validation contracts and four-language metrics

- [x] 11.1 Version the degraded analysis suite/truth without rewriting A1/P5 history, recording source/profile/scope/product digests, language, expected mode, candidate kind, formal assessment and failure class.
- [x] 11.2 Extend validation runners and schemas to compare ast-ir/ir-only/ast-only/failed plus source/formal candidates while keeping truth independent from current analyzer observations.
- [x] 11.3 Report C11, C17, C++17 and C++20 planned/completed/eligible, mode counts, source/formal candidates, TP/FP/FN, exact match, strict/supported-only metrics and abstention separately; zero denominators remain null.
- [x] 11.4 Add validation gate tests proving a C++ false positive fails its profile even when C and aggregate metrics pass, and C profile absence cannot be hidden by C++ results.
- [x] 11.5 Measure cold/warm stage wall/CPU, peak RSS, artifact bytes and cache hits/misses; assert semantic equality of modes, failures, slices, candidates and formal assessments.
- [x] 11.6 Add deterministic sampling/adjudication records for eligible archived regressions while keeping Windows, invalid and unsupported samples excluded from accuracy calculations.

## 12. Unit tests and coverage enforcement

- [x] 12.1 Add effective unit tests for all new/modified C++ modules and executable headers, covering normal, boundary, exception, budget and unknown paths; ensure every owned source is linked/enumerated.
- [x] 12.2 Add effective unit tests for all new/modified Python orchestration, schema, failure, availability, candidate, slice, gap, cache, CLI, validation and report modules, including files not imported by happy-path tests.
- [x] 12.3 Extend the quality inventory and threshold logic so project overall, C++, Python and every affected owned module report line/branch hit/total and each metric is at least 90%; missing reports and 89.99% fail.
- [x] 12.4 Keep integration and semantic fixture profiles separate from unit coverage, list all excluded third-party/generated/test-input files with reasons and reject exclusions of owned business logic.
- [x] 12.5 Run old P1–P4/A1 unit/contract/cache/CLI regressions and prove their default semantic digests and exit behavior remain unchanged.

## 13. Offline integration and final acceptance

- [x] 13.1 Run the complete C11/C17/C++17/C++20 degradation matrix offline in the locked development image without network, SSH, DevKit, external backends, native linking or target execution.
- [x] 13.2 Run focused mutex conservatism acceptance: C same-object pthread safe/risk pair and C++ unknown-RAII regression, verifying no false risk from an unmodeled synchronization gap and no over-broad C abstention.
- [x] 13.3 Run relevant/unrelated cross-TU failure, stage budget, corrupted cache and cold/warm deterministic integration profiles in fresh output directories.
- [x] 13.4 Run full unit and coverage gates and record exact commands, environment/toolchain versions, test counts, overall/language/module line and branch hit/total, scope, exclusions and report locations; every required value must be at least 90%.
- [x] 13.5 Run strict OpenSpec/schema validation, protocol compatibility, documentation links/status/provenance checks and verify no mandatory remote or sibling-project dependency was introduced.
- [x] 13.6 Publish an acceptance manifest with artifact hashes, four-language TP/FP/FN/exact/abstention, modes/failures, performance/cache, mutex regression, exclusions and all gate outcomes; any required failure keeps tasks incomplete.

## 14. Documentation and handoff

- [x] 14.1 Update `README.md` and `doc/README.md` with the degraded analysis entry point, four modes, C/C++ scope, Windows exclusion, exit codes and non-safety-proof warning.
- [x] 14.2 Add `doc/DEGRADED_SOURCE_ANALYSIS.md` covering protocols, failure taxonomy, SourceCandidate boundary, SynchronizationGap, dependency slicing, CLI, cache, bilingual fields and examples for C and C++.
- [x] 14.3 Add `doc/DEGRADED_SOURCE_ANALYSIS_VALIDATION.md` with actual commands, versions/hashes, unit/coverage results, four-language truth metrics, archived-sample eligibility, cold/warm evidence and limitations.
- [x] 14.4 Update `doc/IMPLEMENTATION_ROADMAP.md` and OpenSpec navigation to reflect actual proposed/applying/validated/archived state without marking A3 `std::thread` or A4 RAII support as implemented.
- [x] 14.5 Review every task, report denominator, coverage module and required acceptance artifact; only after all implementation and validation evidence passes mark the change ready to sync/archive.
