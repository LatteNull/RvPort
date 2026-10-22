# Implementation verification record

## Fixed baseline and limits

- Baseline source: Git `7ac4273` (before this change), same standalone image `rvport-kb-scanner-test:local`.
- Fixed small input: `tests/fixtures/source-evidence-chain`, human oracle in that directory; no Make/compiler execution.
- Before/after benchmarks run in separate read-only containers; compare stage timings, peak RSS, JSON bytes, facts/conclusions and summary, not Finding count alone.
- Regression acceptance: small fixture analysis/projection each no more than baseline × 2 + 0.5 s (startup noise allowance). Larger fixture projection no more than baseline × 2 + 2 s; analysis no more than baseline × 1.25 + 2 s. RSS no more than baseline × 2. JSON growth up to 20× only if explained by source windows and real evidence; never shrink the normal 20/20 window to meet it.
- Query limits unchanged: depth 16, visited 256, paths 32. Source contexts cap 256 lines / 65536 characters. Unit assertions verify irrelevant graph growth cannot change query result/visit count and one read/split per file per projector.
- Historical whole-scanner unit gaps explicitly authorized by the user. Scanner-owned `kb_scanner`, `scripts`, `tools` all included (even unimported files); no coverage pragma exclusions. See `tests/source-chain-test-inventory.json`.

## Verification status

Implementation and acceptance complete. Final isolated suite: 481 tests, overall 97.8202% line / 93.3555% branch over all 128 scanner-owned source files in kb_scanner/scripts/tools, with every affected module at least 90/90. Context is 100/100. Historical source remains in the denominator; no Legacy runtime restoration.

Final container command ran the isolated gate, corrected enum gate (128 tests), and full component regression (220 tests, 215.042 seconds) sequentially, exit 0. Earlier default-runner logs retain the stale chain-test-inventory failures; supporting suites were added without lowering thresholds. RPM endpoint regression found early was fixed and remains covered.

Final paired libarchive: analysis 42.449→54.994 s (limit 55.062 s), projection 3.474→4.701 s (limit 8.949 s), RSS 623512→625688 KiB, report 4411143→6150656 bytes. All limits passed, but analysis is near the threshold on a shared host. An earlier concurrent-test round missed the projection threshold; it is retained and not counted as passing. Final report hash equals the fully source-audited and instrumented report.

AVX and libarchive conclusion/summary/fact-non-context fields unchanged. Original small-fixture normalized facts remain a byte-field-identical subset; new Make parameter/recipe facts and associated reference changes are explicitly reviewed. Candidate-noise snapshots unchanged; V1 full canonical hash unchanged; only V2 chain/context hash intentionally updated in a new ledger.

All reports are retained under repository-ignored `.codex-tmp/source-chain-baseline-20260911/`.
