# Source analysis and capability boundaries

English | [简体中文](analysis-capabilities.zh-CN.md)

This document describes existing static capabilities only. Analyzing a scanned project's test source does not execute tests and is separate from excluded E2E infrastructure. Zero hits does not prove that the project compiles or runs.

<a id="doc-architecture-enum-analysis-baseline"></a>

## Architecture enums

### Frozen fact data

| File | SHA-256 |
|---|---|
| `rulesets/riscv-porting/generated/clang-x86-entries.json` | `adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7` |
| `rulesets/riscv-porting/generated/gcc-x86-entries.json` | `22d68c2ab3c8c40c8606451af2e5f493877661d031b6b2f379eff7886c23d191` |

These are the frozen publication digests. Only the GCC source path was sanitized to `vendor/gcc/gcc/config/i386`; fact content is unchanged. Historical report digests identify their original versions and must not be overwritten with current digests. Regression contracts protect current bytes, categories, source identities, and load paths. Enum analysis reuses only loaded `targetFeatures`, `architectureAliases`, and applicable `platformMacros`.

### Behavior

- Bounded inputs include enum declarations, member declarations, and conditional/case references that bind to declared members. Ordinary variables, comments, strings, and arbitrary identifiers do not become enum Evidence.
- Name matches are candidates only. Isolated names remain unknown; upgrading requires a closed declaration → reference → selection → real x86 dependency relationship.
- Template-dependent, dynamic, ambiguous, recovery-parsed, or unbound inputs remain unknown. RISC-V/generic/portable/scalar names are siblings only; ARM supplies context only.
- Default V2 uses existing `architecture_probe`, `source_evidence`, and edge kinds, with details in `org.rvport.kb-scanner.architecture-enum`.
- Explicit V1 retains `CPP.X86.CONSTEXPR_ARCH_BRANCH` for `if constexpr`; other enum candidates use `C_CPP.X86.ARCH_ENUM_CANDIDATE`.

<a id="doc-architecture-candidate-noise-baseline"></a>

## Candidate admission and deduplication

1. Pinned tree-sitter-c 0.24.2 and tree-sitter-cpp 0.23.4 both use `gnu_asm_expression`. Only a complete container produces inline_asm Evidence; qualifiers, constraints, operands, and clobbers do not independently create facts. MS asm has no supported standalone node. Unknown asm structures produce Diagnostics instead of guessed node names. Preserve SourceByteIndex and never access native Point values.
2. asm/attribute facts retain complete text and byte spans. Producers at the same source position merge provenance; distinct positions and explicit compilation contexts remain separate. Global fact identity is unchanged.
3. Foreign-architecture filtering is not an instruction blacklist. Only explicit ARM/AArch64 compiler selectors and traceable same-file macro definitions prove necessary conditions. The name `ARMCRC32` alone is insufficient. Ambiguous or forward definitions, relevant undef, macro cycles, negation, and unsupported expressions cannot justify exclusion.
4. AND needs at least one proven necessary ARM condition; OR needs proof on every side. `x86 || aarch64` retains the x86 clue, and `x86 || UNKNOWN` cannot establish inactivity on RISC-V. An else branch does not inherit the preceding branch's ARM label. Unknown innermost guards conservatively retain candidates; global Boolean solving is outside this scope.
5. An ERROR elsewhere in a file must not contaminate an otherwise complete condition, macro definition, or asm construct. Frontend `structureComplete` checks relevant byte ranges. A foreign `guarded_by` relationship can be complete only when all relevant evidence is locally complete. Keep file diagnostics; incomplete conditions or asm cannot justify exclusion.
6. Detectors prioritize loaded x86 KnowledgeEntry matches. Definite matches are not removed by foreign filtering. Without a definite match, a complete foreign proof suppresses the x86 Observation; other asm becomes `candidateBasis=unclassified_inline_asm`. Attribute candidates require structural names such as target, target_clones, or vector width. Names in strings/comments and ordinary no_sanitize/aligned/visibility attributes are not admitted.
7. Invalid candidates receive structured INFO contract diagnostics and are removed from ClassificationSnapshot, so they never enter Assessment. V1/V2 projectors validate again. Bypassing classification contracts fails projection, preserves existing artifacts, and publishes no new artifacts; it cannot masquerade as successful filtering.

V2 remains default and V1 explicit. Outputs remain `scan-result.json`, `scan-report.html`, and `scan.log`. V1 logs retain diagnostics/readiness only, without a new Finding list. Context may include nearby ARM or ordinary attribute code. Tests check the Finding's hit root, not a ban on those words anywhere in the report.

<a id="doc-architecture-family-analysis"></a>

## Architecture implementation families

### What can be established

Within one authorized file inventory, discover local families such as `foo_x86.cpp` / `foo_generic.cpp` / `foo.cpp`, or `arch/x86/math/foo.cpp` / `arch/riscv/math/foo.cpp`. Path clues can be recorded even without a build database or with empty files. Reuse existing source-file identities without traversing the filesystem again.

Filename prefixes/suffixes and directory role slots are separate templates; the initial implementation supports one slot. Keys preserve full parent directories, paths outside role directories, and extensions. Files are not grouped by basename across vendors/subprojects. Multi-slot conflicts and case collisions remain ambiguous. Files without a role are unlabelled, not automatically generic. Only families with an x86-role candidate enter this catalog; ARM members provide context only.

Terms such as amd64/x64, AVX/SSE, and generic are versioned path heuristics, not newly collected compiler facts. Role hints preserve their original terms and rule names. Family analysis does not modify the GCC/Clang fact JSON files.

### What cannot be inferred

- A generic filename does not prove the absence of AVX; an x86 filename does not prove x86 instruction use.
- Discovering a generic candidate does not clear an existing blocker. Missing generic/RISC-V files do not create portability gaps.
- Compiling two files into one target does not prove they are alternatives. No `alternative_to` relationship or function-equivalence proof is added.
- `discoveryStatus=complete` means supported templates in the authorized inventory were processed, not that all alternative implementations were found.
- Function-multiversion fallbacks, interprocedural value flow, complex macros, and dynamic build semantics are outside family discovery.

### Existing evidence

`candidate_member_of` is a non-executing structural relationship with no fabricated source Evidence; it does not enter the main source chain. Existing proofs can bind after member/configuration validation, preserving selected/inactive/not_selected/unknown and actual source files/lines. Original Evidence, Facts, Classification, Assessment, and proofs are not rewritten.

Source descriptions are binding provenance, not regenerated call chains. Public output contains no internal proof/relation IDs that cannot resolve within the Finding. Existing source chains, highlights, ±20-line context, and `suggestion/suggestion_en` remain.

Locatable Make/CMake source-selection proofs may be displayed. An Autoconf event containing only a variable assignment without a closed file relationship stays unbound/unknown. Family analysis does not additionally interpret shell or build languages.

### Report placement

Default V2 uses `org.rvport.kb-scanner.architecture-family`:

- Top-level `extensions` holds a bounded candidate catalog, including path-only families without code Findings.
- Related Findings embed their own members/bindings in `fact.extensions`, independent of the top-level catalog.
- HTML shows a bounded Chinese family summary with escaped paths. Path-only entries have no fabricated line 1, code highlight, or navigation link.
- Explicit V1 retains existing fields/Findings without path-only pseudo-code Findings.

New explanations use `explanation` / `explanation_en`. Core V2 schemas/enums, the three artifacts, and required backend inputs do not change. Older readers can ignore the extension; enhanced display is opt-in.

### Budgets and limits

Internal defaults: 100,000 paths, 10,000 families, 128 members per family, 4,096 proof bindings/10,000 proof steps, and 10,000 new structural relationships. The V2 catalog is limited to 1,000 families/10,000 members. Each Finding allows 8 families/128 members, each member 32 displayed bindings, and each binding 64 sources.

Truncation has stable reasons and counts. Discovery and display completeness are separate. Template bucketing avoids all-pairs comparisons and repeated proof searches. An incomplete combined frontend conservatively reports source parseStatus as unknown; that does not mean every file is proven to have failed parsing.

Example fixture: `tests/fixtures/architecture-family-demo/`; human grouping oracle: `tests/fixtures/architecture-family-oracle.json`. These establish candidate/selection relationships, not API or behavioral equivalence between example functions.

<a id="doc-function-multiversion-analysis"></a>

## Function multiversioning

### Fixed semantic matrix

Reference date: 2026-09-22. Official references: [GCC function multiversioning](https://gcc.gnu.org/onlinedocs/gcc/Function-Multiversioning.html) and [Clang 18.1 attributes](https://releases.llvm.org/18.1.8/tools/clang/docs/AttributeReference.html#target-clones). The initial rules cover Clang 18.1, x86/x86-64, C/C++ target_clones, and C++ target semantics. Do not extrapolate to other combinations. The scanner's libclang version is not the scanned project's compiler version.

| Construct | Structural conclusion | Default-implementation rule |
|---|---|---|
| A single target specialization | Insufficient proof of a missing default | No gap |
| Different targets on the same function | Local multiversion candidate | Evaluate gaps only with applicable rules and complete local scope |
| Literal target_clones list | One source body with multiple version descriptions | Check the default token and body separately |
| Declaration-only default | Declaration exists | Does not prove an implementation exists |
| Default body contains AVX | Retain original x86 facts | Does not prove RISC-V usability |
| cpu_dispatch/cpu_specific, target_version, macros/pragmas, templates | Unresolved/unsupported | Do not apply these default rules |

Without a reliable compiler version/source-target, the profile stays unknown. Executable names, successful compilation, compiler-fact generator versions, and scanner parser versions do not identify the project compiler. Do not execute probes or add required backend inputs. Unverified combinations report structure and unknown reasons only.

### Implemented capabilities and boundaries

- Tree-sitter materializes relevant attributed free functions and matching declarations only, retaining attribute IDs/values, qualified signatures, owners, and body spans. Optional Clang adds scanner-owned scalars; conflicts do not overwrite the baseline.
- Recognize single-target specializations, multiple target definitions, and shared target_clones bodies. Distinguish default presence, declaration/implementation, group completeness, body dependencies, and target applicability.
- Reuse intrinsic/feature and source/build proofs. Use column spans for same-line matching and exclusion spans for nested bodies. Version members do not imply execution reachability, and occurrences are not multiplied by clone count.
- Complete exclusion must cover the entire relevant attribute group. Cross-configuration, partial, or unknown selection stays unknown. Foreign-guarded attributes do not create new x86 porting issues. A default never revokes an existing confirmed x86/high/blocker conclusion.
- V2 top-level and per-Finding data use `org.rvport.kb-scanner.function-multiversion`, merged with other namespaces. Actual attribute → function → body facts enter the source chain with ±20-line context. Selection bindings show real provenance without dangling proof IDs. V1 retains fields with new rule mappings and bilingual suggestions; core schemas do not change.
- Source, relationship, and display budgets are separate. Semantic bindings and selection provenance share a display budget. Truncation retains counts; an undisplayed default is not a missing default.

Unknown scope includes complex signatures, aliases, methods/templates, macro wrappers, pragmas, cross-TU completeness, cpu_dispatch/IFUNC, runtime selection, interprocedural behavioral equivalence, and real target compilation. No required backend inputs or project/compiler probes are added.

<a id="doc-macro-and-build-effect-proofs"></a>

## Macro and build-argument effects

### Observable relationships

For `OUTER(_mm256_add_epi32, value)`, the argument is a raw fact. A proven `OUTER → INNER → fn(value)` binding connects back to its actual line/column. A Finding can trace argument origin, real recipe/target use, preprocessing conditions, macro definitions, parameters/replacements, and the final intrinsic. Knowledge matching remains a side branch. Context stays at ±20 lines with highlights; classification/assessment stages are not inserted.

Declaring a variable does not prove argument consumption. `store(fn)` or an unused fn does not prove fn was called. Retain raw arguments and compiler-knowledge hits as candidate/unknown for later analysis. These proofs do not establish equivalent generic/RISC-V implementations, usage exclusion, or successful builds. Missing new proofs do not revoke confirmed x86 facts.

### Initial supported scope

| Supported | Unknown / limits |
|---|---|
| Static Make includes, conditions, four assignment timings, single-source recipe `$@/$<`, multiple `-D/-U` sources | shell/eval/dynamic includes, pattern/target-specific rules, other automatic variables, response files, unknown compiler wrappers |
| Existing CMake target/source/link usage, equivalent-definition merges, explicit same-command option order | Conflicting propagation origins or unproven overrides; configure is not executed |
| Per-TU/configuration define/undef, object aliases at use time, bounded integer/Boolean conditions, feasible-path merges | Unmodeled arithmetic/types/platform builtins, unknown include side effects, pragma macro stacks, complex expressions |
| Fixed parameters, nested forwarding, raw argument positions, isolated invocation identities | Stringification, token pasting, variadics, recursion, template commas, unrecoverable token structures |
| Reverse lookup of macro demands from official knowledge while retaining all raw records/facts | Index matches are not effect proofs; invocation environments still need validation |

Tree-sitter records contain Python scalars and source spans only. Clang tokens are copied while the TU is alive; Cursor/Node/Tree objects never enter later stages. A compilation database observes a source configuration; it does not prove target RISC-V selection. A shared header can be selected/inactive in different TUs. One Finding displays independent occurrences; configuration conflicts make the overall chain ambiguous, and primaryPath never joins configurations.

### Budgets and output

- 100,000 events per TU; include depth 16/count 128; Make include depth 8/count 128.
- Per-call expansion depth 32 and 4,096 tokens. At most 100,000 new effect relationships per scan; inherited graphs do not consume this quota. Rejected relationships leave no orphan entities.
- Source queries retain depth 16, 256 visits, and 32 paths. Each context is capped at 256 lines/65,536 characters. Truncation preserves raw facts and unknown states; incomplete proofs cannot reduce risk.
- V2 retains `steps/edges/occurrences`. `fact.extensions.org.rvport.kb-scanner.macro-effects` adds bounded effect descriptions, configurations, TUs, proof status, reasonCodes, Chinese `description`, and English `description_en`. Display at most 32 effect configurations and report clipping with totalUses/truncated.
- V2 remains default, V1 requires `--schema-version 1.0`, and outputs remain JSON/HTML/log. V1 adds no core fields but can add actual provenance to existing traces.

<a id="doc-test-content-analysis"></a>

## Static relationships in test source

### Observable evidence

An intrinsic Finding can carry actual provenance such as:

```text
CMake add_test → source members of a local executable
                       ↓
                  main / one-hop callsite → helper function → assert form → intrinsic
```

This is not a fixed concatenated display order. Edges require actual evidence. An uncalled function may show lexical ownership but cannot be presented as content validated by main. Source nodes retain hit locations and ±20-line context; budget clipping is explicit. Classification/assessment are not source steps.

One Finding separates three axes:

| Axis | Meaning |
|---|---|
| `buildStatus` | Whether the source belongs to the configuration's build target |
| `registrationStatus` | Whether the test is registered, enabled, or architecture-excluded |
| `content.entryStatus` / `content.relation` | Whether the source entry, one-hop call, assertion argument, or local value relationship is provable |

A `DISABLED TRUE` test may still need to compile an x86 intrinsic; disabled registration cannot reduce independent compilation risk. An entry point does not prove execution, passing tests, or complete coverage.

### Initial support and unknown cases

- CMake: `enable_testing()`, `add_test(NAME … COMMAND local ordinary executable …)`, and ordered literal same-directory `DISABLED` properties. Resolve forward references and directory scope separately.
- Old signatures, wrappers, dynamic discovery, registration inside functions/macros, and unsupported properties/filter arguments remain candidate/unknown. CMake/CTest/Make are never executed.
- Reuse existing Make/RPM/CTest assets and membership. Historical `confirmed` build assets are not C++ entry proofs; new content context retains entry/registration breaks.
- Support a unique ordinary `main`, a unique ordinary direct one-hop call in the same file, direct assert arguments, and scalar single initialization → assert use in one straight-line block.
- Do not fabricate complete proofs for overloads/separate declarations, unknown included declarations, templates, member/indirect calls, recursion, cross-TU/second-hop calls, nested lambdas, control conditions, overwrites/escapes, or damaged syntax.
- Standard `assert` identity is not inferred from its name. With an existing Clang context, exact supported glibc system-header macro definitions and actual expansions can show enabled/disabled state, including `NDEBUG`, for that **observed TU**. Other libc/profiles, unknown macro overrides, and missing compilation databases remain unknown. Observed x86 configuration is not automatically RISC-V proof.
- `value == 42` and `sizeof(long) == 8` do not independently create architecture Findings. Codec data enums retain existing usage-admission rules; assertion shape does not upgrade them to execution dependencies.
- Complete registration/assertion semantics for third-party test frameworks and deep call graphs are deferred. Signed shifts remain the final low-priority target.

### Compatible output

V2 core schema, required fields, backend inputs, and the three artifacts are unchanged. Optional data appears at:

```text
findings[].fact.extensions["org.rvport.kb-scanner.test-content"]
  uses[]: testName, configuration, role,
          buildStatus, registrationStatus, proofStatus,
          content, assertion, reasonCodes, sourceIds,
          description, description_en
  sources[]: id, symbol, source(file/span/context/highlights)
  totalUses, truncated, limit, sourceLimit
```

Each Finding's `sourceIds` resolves internally. `assertion.observedConfigurations` is a static observation of the current compiled TU without external Evidence-ID dependencies. Extensions merge with family, multiversion, candidate-usage, and macro-effects extensions rather than replacing them. HTML defaults to Chinese with escaping, and existing `suggestion/suggestion_en` remains. Explicit V1 retains old fields without requiring this namespace.

<a id="doc-candidate-usage-proofs"></a>

## Candidate usage proofs

### Capabilities and limitations

The default pipeline passes loaded knowledge to the frontend. While native trees are alive, it pre-normalizes original Evidence with the official rules, matches candidates, and collects complete usage records only for matching scopes. Preselection may share a representative for equal kind/value references, then expands all original occurrences after matching. The official Normalizer still validates declarations/references, and final normalization retains every raw fact. After source/build/test/family/multiversion analysis, exact usage-query roots come from final candidate facts. Matching and GCC/Clang data are reused; codec names, algorithm names, or human review labels never justify exclusions.

Non-candidate functions no longer produce usage_scope or consume scan-level usage-record budgets. Selected functions still require complete collection, not just hit lines. Collection demand is not an exclusion proof: final facts and consumer gates validate configurations, bindings, scope closure, and execution conflicts. Node/Tree objects do not cross stages, and source is not reread per Finding.

In ordinary functions, uniquely bound local enums, explicit integer-scalar copies/comparisons, and non-escaping fixed local-array writes can form a pure-data closure. The default CLI's local-enum positive case covers automatic collection → normalization → usage graph → consumer validation → candidate Classification omission → V2 exclusion audit, without manually injected roles.

Calls, returns, field/pointer writes, address-taking, volatile, unsupported operations/control, syntax errors, open definitions, cross-configuration input, or exhausted budgets cannot justify exclusion. Macro definitions, complex expansions, templates, and interprocedural analysis are not fully implemented. Scoped enum names do not degrade to same-name local-variable bindings. Generic/RISC-V files do not establish equivalent executing implementations.

The automatic role is `non_execution_data`, not an automatic claim of algorithm, data_format, or output_platform. Usage roles do not prove compilation and cannot replace target selection, alternative-implementation, or readiness evidence. Even a call name containing portable is not a safety proof.

Confirmed x86 dependencies inside the actual closure reuse the official matcher/compiler facts, reporting `usage-known-execution-conflict`, counts, and sources. Only the same subject/configuration closure is checked; an intrinsic elsewhere in the file does not contaminate it. Detectors use an Evidence reverse index to isolate non-executing usage graphs rather than traversing the entire graph per candidate.

When a compilation database exists, an unconfigured Tree-sitter inventory cannot represent one of its configurations. Only exact configuration correspondence qualifies as proof. Tests cover this boundary with the default Tree-sitter path and explicitly injected optional Clang multiconfiguration components.

### Internal contract

Candidate roots are exactly `factId + subjectId + configuration + matchedEvidenceIds`. Usage records are extracted during native Tree lifetime and contain only scalars/project-relative spans. Later stages retain no Node/Point. New records append without rewriting old facts.

`usage_scope` retains function spans, all collected records, declaration bindings, and incomplete reasons. Normalization checks parent/child endpoints, ranges, order, bindings, and configuration. Conflicting producers cannot become complete.

Queries reuse scope indexes. Closures include relevant reads/writes, declarations/value flow, controlled statements, and escapes. `usage_record`, `usage_scope_coverage`, `usage_dependency`, and `usage_scope_member` are non-executing relationships marked `semanticRole=non_executing_usage`; they are not build selection or alternative_to proofs.

An automatic proof may use one has_semantic_role summary edge, but it must carry usageProof so consumers can revalidate:

- Exact root, configuration, and original matched Evidence set.
- Nonempty source records, scope summaries, complete supporting relationships, and sources.
- Matching expected and actual usage counts.
- Closed record/scope membership, with every supporting record reachable from the query root.
- No unresolved state, conflict, escape, or truncation; a nonempty continuous ProofPath containing the role edge.

Consumers never trust scopeComplete/complete alone. Original Observations and facts remain; only admitted candidate Classifications are omitted. Confirmed execution dependencies take precedence.

### Budgets

| Layer | Hard limit |
|---|---|
| File syntax traversal | 100,000 nodes |
| Usage records per function | 10,000 |
| New usage records per scan | 100,000 |
| Closure per root | Depth 32, 4,096 nodes, 8,192 supporting relationships |
| Query visits per scan | 1,000,000 |
| Finding display | 64 candidate roots sharing 64 source records |
| Top-level exclusion audit | 100 entries, up to 64 source records each |

Scope-membership edges count against supporting-relationship budgets, not just value-flow edges. Tests may lower limits but cannot exceed them. Exceeding limits retains facts, disables exclusion eligibility, and records truncated/reasonCodes and budget state in summaries.

Once collection is demonstrably exhausted, retain raw facts, collected records, exact hits, and budget reasons, then return unknown without building a closure that cannot prove completeness. Query visits are then zero; audit sources are located hits, not usage records from an unperformed query. Non-budget partial states continue normal break queries. `cacheHits` measures usage-query caching, excluding internal projection/materialization/consumer caches.

Source context reuses SourceContextProjector: ±20 lines, at most 256 lines/65,536 characters, with highlights. Display truncation does not change classification.

### V2 extension

Namespace: `org.rvport.kb-scanner.candidate-usage`. No new core schemaVersion, required fields, or enums.

- Finding `fact.extensions`: `version/rootCount/omittedRoots/roots`. Each root includes symbol, configuration, usage state, producerStatus, reason/reasonCodes, statistics, analysis budgets, and self-contained sources.
- Top-level `extensions`: `excludedCount/omittedExcludedCandidates/excludedCandidates`, containing only admitted candidates without a Classification. `producerStatus=complete` alone never claims exclusion.
- Sources use the existing file/span/context shape, without dangling internal proof/relation typed refs. Multiple roots do not merge configurations or silently discard sources.
- Per-root `projectionStatus` and omitted/missing source counts describe display completeness; `analysisTruncated` describes analysis completeness. They are distinct.
- `explanation/explanation_en` provides Chinese/English. HTML defaults to Chinese, escapes symbols/paths/code, and highlights hits. Semantic roles, classification, and assessment are not source steps.

Bounded structural example; counts illustrate fields rather than a project scan:

```json
{
  "org.rvport.kb-scanner.candidate-usage": {
    "version": 1,
    "excludedCount": 0,
    "omittedExcludedCandidates": 0,
    "excludedCandidates": [],
    "statistics": {
      "rootCount": 0,
      "scopeIndexes": 0,
      "recordCount": 0,
      "visits": 0,
      "cacheHits": 0
    },
    "explanation": "排除仅针对已证明的局部非执行用途，不证明替代实现或项目已可迁移。",
    "explanation_en": "Exclusions concern proven local non-execution usage only, not alternative implementations or project readiness."
  }
}
```

With no candidates, this extension is absent; the empty example is not actual no-candidate output. Default V2, explicit V1, and JSON/HTML/log remain. V1 does not add this extension. Existing classifiers record exclusions through aggregated INFO diagnostics.

The 2026-09-23 fixed-sample review appends to `tests/fixtures/candidate-usage-report-differential.json` without overwriting prior CMake/multiversion ledgers. source-evidence-chain and architecture-enum add only V2 top-level and candidate-fact usage namespaces, with no automatic exclusions. Conclusions, IDs, source main chains, and summaries remain unchanged. All three V1 artifacts/logs for four fixed samples remain unchanged, as do the V2 artifacts for the other two samples.

`tests/audit_candidate_usage_reports.py <new-output-directory-in-container>` generates V1/V2 artifacts for four fixed samples with the new collection/Analyzer disabled and enabled, plus field-level `audit.json`. Run it in an isolated test container; mount a separate persistent output directory if needed. It collects differences without approving them or updating goldens. Formal regressions and coverage gates still follow human review.
