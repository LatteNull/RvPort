# Bilingual floating-point evidence-step descriptions

English | [简体中文](evidence-step-descriptions.zh-CN.md)

Tool 0.5.1 retains public `schemaVersion: 2.0` and adds `title/titleEn/reason/reasonEn` to each `evidenceChain.steps[]`. Titles are limited to 512 characters and reasons to 4,096; whitespace-only strings are forbidden. Consumers enforcing the old schema need coordinated updates. Historical reports are not backfilled automatically.

## Description sources

| Reference | Description basis |
|---|---|
| sourceFact | Fact kind, function, type, relative location, and actual operation/call attributes |
| irFact | Opcode, function, result/operand types, fast-math flags, and debug location |
| binding | Matching method, confidence, and correspondence |
| profile | Target triple, ABI, long-double layout, and declared floating-point capabilities |
| buildContext | context_id, target ABI, and declared build capabilities; commands are not copied |
| compileOption | Effective normalized floating-point options for this scan |
| assessment | Rule, assessment status, reasonCode, and rule-specific limitations |
| conclusion | Existing Chinese/English title and conclusion of the Finding |

AST accumulation does not mean LLVM reassociation occurred, and a profile does not imply hardware testing. Missing references yield `step_description_unavailable`; ambiguous source semantics yield `source_semantics_ambiguous`; unfinished assessments yield `assessment_not_complete`. The step becomes unknown and the chain partial, with an auditable break.

## Stability and safety

Build typed indexes once per scan. Description generation calls no external services and does not reread source. Indexes are not cached across scans; existing fact caches remain version/content keyed, and new results are always reprojected. Wording changes do not recompute Finding/step/edge identities, relationships, or risk levels. The full result digest normally includes evidence-chain changes.

Summarize allowed fact attributes only. Safe relative paths may be displayed; absolute paths, URLs, and credential assignments are sanitized. Fields are length-bounded. Existing output budgets continue truncating whole Findings only. Missing IR attributes are not assumed enabled.

The backend preserves these fields and returns them through existing details without new endpoints, database columns, or frontend code. Historical records remain readable without the fields; rescanning generates them. Archive registration reuses existing floating-point report handling.

## Validation

Run `make coverage` inside the Linux container. Include all project-owned Python source, including unloaded modules; overall and affected-module line/branch coverage must each reach 90%. `step_descriptions` is included in the gate. Run `pytest -q tests/integration` for real Clang validation. Rebuild the IR worker at tool version 0.5.1 as well to avoid version-lock failures.
