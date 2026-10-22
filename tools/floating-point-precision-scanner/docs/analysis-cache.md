# Analysis cache maintenance

English | [简体中文](analysis-cache.zh-CN.md)

Schema 1.4 provides `off`, `read-only`, `write-only`, and `read-write` modes. The cache root must be an absolute path inside the project root. Only `source-facts`, `ir-facts`, and `evidence` are cached; final findings, assessments, suppressions, and scan results are not.

Each key includes cache schema, object kind, and semantic inputs: source/compilation context, profiles, producer/Clang/LLVM versions, artifact digests, mapping configuration, and relevant logical budgets. Entry envelopes validate kind, schema, key, payload size, SHA-256, and dependency digests. Reads reject symlinks, escaping paths, oversized, damaged, or incompatible entries, producing bilingual diagnostics and a cache miss. If recomputation fails, normal analysis-failure semantics apply.

Publication uses a same-directory temporary file, flush, fsync, and atomic replacement. Concurrent writers for one key may publish only the same payload digest. Conflicts or publication failures do not overwrite valid entries. Statistics appear in `org.rvport.floating-point-scanner.runtime.cache`, but cold/hot hit counts do not enter the scan semantic digest. Roll back by setting mode to `off`; the cache directory is removable derived data.

Unit tests cover hits/misses, all four modes, changed inputs, damaged envelopes, digest conflicts, size limits, symlinks, fsync failures, publication conflicts, and equivalent cold/hot semantics for source/IR/evidence.

Facts 1.4 / mapper 1.1 changed source classification, canonical scalar types, and blocking dependencies. Source-facts keys therefore also include facts schema, mapper version, and source-location revision 4. Old facts 1.3 entries must be ordinary misses; never patch fields in place or reuse them for new assessments. Cold recomputation and new-version hot caches must produce identical assessments, findings, diagnostics, stable IDs, ordering, and semantic digests.
