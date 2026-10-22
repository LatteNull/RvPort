# Build-selection support matrix

English | [简体中文](build-support.zh-CN.md)

This matrix describes the static analysis boundaries for current build inputs. All inputs are read-only; the scanner does not execute project commands.

| Input | Supported | Partial / unknown | Deferred |
|---|---|---|---|
| GNU Make | Literal/variable assignments, known references, conditions, static includes, source/argument/dependency/target relationships | Dynamic functions/includes, loops, budget truncation, ordinary shell commands | Full Make semantics and recipe execution |
| configure / config.guess / config.sub | Scanner-owned AST, bounded variables/parameter trimming, first-match case semantics, simple if/test, exact `uname -m`, restricted output/exit, literal helper calls and cross-file evidence | Unknown OS/libc/arguments, external commands, complex shell, path/syntax/graph budgets; unbound local rejection does not become a project blocker | Script execution, helper regeneration or downloads |
| configure.ac / M4 | Parenthesis-free canonical declarations, multiline literal AUX_DIR/SUBDIRS, configuration units and colocated helper pairs; existing raw M4 facts retained | Declarations do not prove execution; missing helpers, dynamic directories/macro expansion, syscmd/esyscmd/include | Autom4te/M4 evaluation and tracking future generated versions |
| CMake | Existing File API JSON; bounded commands, conditions, target/source/link usage and argument provenance in CMakeLists.txt and ordinary .cmake files | Dynamic expressions, unknown schemas, dangling references, conflicting configurations, unproven definition override order | Running configure and full CMake DSL evaluation |
| Meson | Existing introspection JSON | Missing architecture, unknown versions/fields, conflicting configurations | `meson setup` and Meson DSL interpretation |
| CTest | Existing JSON, explicit test roles/targets/sources/arguments/dependencies and static selection relationships | Dynamic commands, missing targets/sources, name-only candidates | Test execution and pass status |
| Compilation database | Source/arguments from existing contexts and explicit target provenance | Missing targets and conflicting contexts | Starting compilers or generating a database |
| RPM spec | Subpackages/sections, if/elif/else and ifarch/ifnarch, bounded macro environments, ExclusiveArch/ExcludeArch, Requires/BuildRequires/Recommends, script uname/if/case, argument/source assignments and occurrence proof graphs | External/parameterized macros, rich dependencies, unknown script side effects, include/Lua, malformed structures, exhausted budgets, whether script arguments actually enter the build | Full RPM/specfile evaluation, package availability, build execution |

## `uname -m`

An exact `uname -m` without a wrapper, pipe, redirection, or extra command is a symbolic architecture selector. It uses the RISC-V target from ScanContext directly without executing anything or modeling cross-compilation misselection. Each build language uses its own supported conditional semantics; there is no cross-language, file-wide rule that assumes RISC-V takes precedence or that a generic fallback exists.

Autoconf follows first-match case semantics and bounded if evaluation. `*) exit 1` rejects; it is not generic support. Helpers must produce a valid name and exit successfully, and the configuration chain must show an actual call. The absence of a literal riscv branch alone is not a gap. See [Autoconf analysis](#doc-autoconf-target-support).

RPM script cases also follow actual first-match order, not branch-name heuristics. An optional x86 optimization does not prove a missing required path. Definite gaps currently require a complete, activated architecture restriction; an unproven mandatory script path is not upgraded. Selected argument/source assignments do not by themselves prove real build consumption.

Target-adapted dependencies retain their Facts. A fixed x86 Finding is suppressed only when relevant expansion and upstream proofs are complete. A selected `Recommends` dependency is not automatically blocking.

<a id="doc-autoconf-target-support"></a>

## Autoconf configuration chains

### Inputs, configuration units, and targets

- Discover `configure`, `config.guess`, `config.sub`, `configure.ac`, and `.m4` files within the authorized read-only workspace, respecting exclusions and rejecting symlinks that escape it.
- Derive the target CPU only from existing `target_arch`. Exact `uname -m` is symbolic RISC-V selection; cross-compilation misselection is not modeled. Unknown OS/release/libc/ABI values are not taken from the host, container, or x86 compilation database. Keep build/host/target variables separate.
- Preserve locations for parenthesis-free canonical declarations and multiline literal AUX_DIR/SUBDIRS. Default helper discovery checks only the current, parent, and grandparent directories. guess/sub must be colocated; files from different vendors are never paired.
- Distinguish configuration units by directory and record entries separately. Subproject and auxiliary-directory declarations do not prove execution. Remote x86 artifacts and future bootstrap outputs absent from the inputs are not considered analyzed.
- Preserve raw M4 facts and unselected shell branches, but do not use old keyword-based gap logic to upgrade them to acceptance or rejection.

The default exclusions include `build`. Helpers under an excluded `build/autoconf` directory are unavailable/unknown. The existing `--exclude .git` option can adjust the input scope; no new option is required.

### Static semantics

Supported constructs include literals/quotes, simple variables and concatenation, `${v#p}`/`${v##p}`/`${v%p}`/`${v%%p}`, first-match and nested case with literals/`*`/`?`/ordinary character classes/`|`, simple string test/if/elif/else, restricted echo/printf and exit, and bounded literal helper calls within the workspace.

| Case | Result |
|---|---|
| `*) exit 1` precedes a riscv branch | Rejection; the later branch cannot recover it |
| A generic branch emits a valid target name and exits successfully | Local script acceptance; no gap merely for lacking a riscv literal |
| guess output reaches an actual literal sub call, which rejects it | Preserve the cross-file call, output, and rejection chain |
| exit 0 without valid helper output | Normalized unknown |
| An isolated sub has an unbound `$1` | Do not invent a complete triplet or a project blocker |
| Unknown platform, dynamic command, complex shell, or exhausted budget | Unknown; retain facts and do not execute the project |

Loops/functions, eval, dynamic source, complex redirection, field splitting/globbing, and case fallthrough are unsupported. Unknown side effects stop subsequent inference rather than reusing an invalid environment; raw syntax facts remain. Calling a child script does not implicitly change the configuration unit's working directory.

Budgets: 4 MiB per file, 64 MiB of total Autoconf reads, 256 entries; 100,000 AST nodes and depth 64; 100,000 M4 declarations; 100,000 execution steps and 128 states; helper-call depth 8. Graph limits remain 10,000 relationships and 4,096 paths; V2 keeps its existing display budget. Exceeding a limit degrades completeness, never proves rejection or readiness.

### Compatible output and limits

A complete, bound configuration rejection uses the existing `missing_riscv_selection_path` as a non-blocking porting issue. Incomplete inputs use `build_selection_unknown`. Acceptance does not mean compilation, linking, or testing succeeded.

Source-event SHA-256, directory unit, entry, target, and parent events live in the existing `extensions.org.rvport.kb-scanner.autoconf` namespace without new schema fields or enums. Existing reasons, Chinese `suggestion`, English `suggestion_en`, ±20 lines of context, and highlights remain. The main chain has no classification/assessment nodes.

Default V2, explicit V1, and `scan-result.json`/`scan-report.html`/`scan.log` remain unchanged. HTML keeps its summary presentation without new frontend interactions. A compilation database cannot substitute for script text.

The fixed GNU scripts shipped with GCC 4.8.0 and 14.2.0 both yield unknown. Missing riscv literals in the older version do not prove rejection; their presence in the newer version does not bypass external commands and unknown platform values to prove complete acceptance. This is bounded static analysis, not a full GNU shell interpreter.

See the [fixed fixtures](../tests/fixtures/autoconf-target/README.en.md) for sources, licenses, hashes, and human oracles. The isolated test image is `rvport-kb-scanner-test:local`; this analysis adds no dependencies or production image/Compose changes. Current commands are in the development guide, and historical acceptance is recorded in the relevant OpenSpec `verification.md`. Overall and affected-module line/branch coverage must both reach 90%; real-parser/CLI tests do not count toward the isolated unit gate.
