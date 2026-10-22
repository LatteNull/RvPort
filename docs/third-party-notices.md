# Third-party provenance and retained notices

English | [简体中文](第三方来源说明.md)

This document records third-party materials and notice locations. RvPort's own code is covered by the repository's [Apache License 2.0](../LICENSE); third-party materials retain their own licenses. The repository is [RvPort/RvPort](https://github.com/RvPort/RvPort). Frontend assets were supplied with the frontend; maintainers must still confirm their provenance and authorization before publication.

## Materials retained with the source

| Material | Source and notices | Use and retention |
|---|---|---|
| GNU `config.guess` and `config.sub` inputs for KB Scanner | File headers and `COPYING3` in `tools/kb-scanner/tests/fixtures/autoconf-target/gnu/` | Retain attribution, license, and exception terms. Used only as static parser input, never as host commands |
| libarchive Autoconf test inputs | `libarchive/COPYING` alongside the fixtures | Retain notices and provenance layout. Exclude upstream files from owned business-code coverage |
| Source snippets in AVX scan reports | [Triple-Z/AVX-AVX2-Example-Code](https://github.com/Triple-Z/AVX-AVX2-Example-Code), which declares BSD-3-Clause | Retain author attribution in reports and the supplied [AVX-LICENSE](../tools/kb-scanner/tests/fixtures/source-evidence-chain/AVX-LICENSE). Original report contents, IDs, and hashes remain unchanged |
| Four LLVM bitcode floating-point fixtures | Adjacent C source, generation commands, and SHA-256 table in the [fixture guide](../tools/floating-point-precision-scanner/tests/fixtures/bitcode/README.en.md) | Retain required fixed inputs. Docker llvm-dis inspection found only `/workspace` and relative paths, with no internal working directories |
| Minimal regression fixtures from earlier memory-order tools | Each fixture directory's `provenance.json` and `sample-inventory.json` record original paths, hashes, and rewriting reasons | Retain provenance. Maintainers must confirm authorization for materials whose original license was unspecified |
| Six frontend SVGs, one AVIF, and favicon | Product assets in the delivered frontend baseline | Rendered branding reads RvPort. Embedded SVG images and the AVIF are abstract backgrounds; the favicon has no text. No account or environment screenshots were found. The AVIF has no metadata and the ICO contains size information only. Maintainers remain responsible for authorization |

GNU, libarchive, and AVX author contact details found by email scanning come from these public materials; attribution is not replaced as internal environment data. `git@github.com` is SSH URL syntax. Example email addresses use example or test-only domains. Scan records retain file locations and domains without copying original email values.

## Dependencies downloaded in Docker

MinIO is built from a pinned official commit. The archive SHA-256, upstream URL, AGPL notice location, and build process are documented in the [object-storage guide](../infra/minio/README.md). Upstream LICENSE and NOTICE files are retained in the runtime image. MinIO's license is separate from the license for RvPort-owned code.

LLVM, the JDK, Node.js, and npm/Python/Maven dependencies use their respective upstream releases and pinned versions. Downloaded source, package caches, and image exports are not included in the repository. Retain the license notices distributed with third-party packages.
