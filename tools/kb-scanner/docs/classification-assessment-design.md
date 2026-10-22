# Classification and static assessment

English | [简体中文](classification-assessment-design.zh-CN.md)

All conclusions apply to static inputs. The scanner does not build or test a project or query the network to fill missing evidence.

## Four layers

1. **Test assets:** CTest targets, RPM `%check` sections, and source membership provide asset evidence. A test-like name is only a candidate.
2. **Test selection:** The evidence graph must close the relevant proof before selection becomes `selected`, `inactive`, or `not_selected`. Otherwise it stays `unknown`.
3. **Classification:** Preserve the Observation and classify it as blocking, actionable but non-blocking, guarded/inactive, a hint, or unknown. Unknown evidence takes precedence over an unsupported definite conclusion.
4. **Assessment:** Evaluate input completeness, target reachability, x86 dependencies, alternatives, test selection/coverage, and packaging separately, then combine them conservatively.

## Candidate treatment

An architecture-like enum name is only a candidate. An isolated name remains unknown and non-actionable. A bound real x86 dependency with unknown selection can be actionable but non-blocking. A proven target-selected x86 dependency can block. A completely excluded path is guarded/inactive.

Zero blockers alone does not establish readiness.

## Meaning of readiness

`riscv_ready` means that the current static inputs are complete, the relevant RISC-V or generic path is proven, no blockers or unresolved unknowns remain, and applicable test relationships are statically established. It always carries `staticScopeOnly=true`, `compiled=false`, and `testsExecuted=false`.

## Projection and compatibility

Schema 2.0 is the default; schema 1.0 requires explicit selection. Both use independent projections of the same snapshots. Qualification runs can use a no-op Projector without publishing reports. Legacy YAML rules do not form a second pipeline.
