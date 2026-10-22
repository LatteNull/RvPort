# Validation corpus and performance baselines

English | [简体中文](validation.zh-CN.md)

Run all Python/Make commands below inside the Docker development container; build instructions are in the tool README. Keep accepted historical baselines separate from current run reports. Tests must not automatically rewrite oracles.

<a id="doc-validation-corpus"></a>

## Human-reviewed corpus

`tests/fixtures/validation/reviewed-corpus-v1.json` is the versioned oracle, and `reviewed-observed-v1.json` is its accepted minimal observation set. Real validation runs can supply V2 results directly per case. The validator extracts Finding keys, states, and lifecycle audits from `conclusion`, analysis assessments, diagnostics, and suppression extensions, then compares them with the oracle. Neither file may be rewritten automatically by the current implementation during validation. Case changes require reviewer, review revision, fixture digest, review basis, and corresponding observation updates, with truth evidence explained in code review.

Each of ten rules has at least 6 positive, 6 negative, and 3 unknown/unsupported cases. Coverage includes C11/C17/C++17/C++20, x86/RISC-V profiles, AST-only, shared BC, AST↔IR evidence, suppressions, budgets, and exceptional lifecycles. Strict recall counts abstained positives as false negatives. Supported-only metrics exclude only cases explicitly marked unsupported by the oracle. Zero denominators return `null`.

```text
python -m floating_point_precision_scanner.validation --corpus tests/fixtures/validation/reviewed-corpus-v1.json --observed tests/fixtures/validation/reviewed-observed-v1.json --output artifacts/validation/validation-result.json
```

Each rule requires at least 90% strict precision and recall, overall exact match at least 95%, and lifecycle cases 100% exact. Reports sort stably by case/rule and record corpus, oracle, tool, and protocol-version digests.

`repair-floating-point-evidence-pipeline` adds no rules or oracle truth changes. It adds evidence-boundary regressions for Clang virtual positions, system math headers, project macros/headers, typedef/auto, pointers/function pointers/containers, genuinely missing types, matched+unknown in one TU, system long-double flooding, real multi-ABI boundaries, old facts caches, and AST-only analysis. Do not improve quality metrics by dropping unknowns, changing support denominators, or hiding diagnostics. Candidate-scope/rule-version changes require explicit review-revision and observation updates.

<a id="doc-benchmark"></a>

## Fixed performance baseline

Accept benchmarks only in `Dockerfile.dev`'s pinned Linux/amd64, Clang/LLVM 21.1.8, 4-vCPU, 4-GiB, network-disabled environment. S/M/L workloads contain 20/100/500 TUs and approximately 10k/50k/250k source lines. Each TU has one analyzable floating-point function plus deterministic padding. Run three cold and three hot trials per size and use medians; run once in a different absolute workspace to verify materialization-independent semantic identity.

Absolute gates: cold wall time 60/240/900 seconds, CPU 180/720/2700 seconds, RSS 1.5/2.5/3.5 GiB, and result size 16/64/256 MiB. Hot wall time must be at most 60% of cold time. Wall/CPU/RSS regressions against `tests/fixtures/benchmark/accepted-baseline-v1.json` must not exceed 20%. Maintainers may review baseline updates only with the same pinned image and workload digest.

```text
docker build -f Dockerfile.dev -t rvport-fp-scanner:validate .
docker run --rm --cpus=4 --memory=4g --network=none -v <artifact-dir>:/workspace/artifacts rvport-fp-scanner:validate sh -lc "make benchmark"
```

Insufficient environment resources require `environment_applicable=false` and a failed gate, not relaxed thresholds. Reports are saved to `artifacts/benchmark/benchmark-result.json`. Determinism directly compares V2 `scan.semanticDigest`. Actual wall/CPU/RSS, cold/hot cache counts, and bilingual presentation text are excluded from that digest and do not affect Finding/evidence-chain identity.

Evidence hardening does not change S/M/L workloads or budgets. The first facts 1.4 run may safely miss old caches and recompute, but the second hot run must still meet the existing 60% wall-time ratio and remain semantically equivalent. New candidate-level assessment counts enter result-size and rule-assessment budgets. Do not aggregate away matched/unknown denominators or hide diagnostics to pass benchmarks.
