# Embedded source context in specialized Finding details

English | [简体中文](specialized-finding-code-context.zh-CN.md)

## Request

```http
GET /api/projects/{projectId}/floating-point-findings/{findingId}
GET /api/projects/{projectId}/memory-order-findings/{findingId}
```

Use existing login sessions/project access controls. Clients submit no source path, revision, or context size; the backend reads them from the Finding. Each endpoint accepts Findings of its own analysis type only.

## Response

Existing detail APIs retain their data/traceId/timestamp envelope and Finding fields, adding data.codeContext and data.codeContextUnavailableReason. On success the latter is null. codeContext fields:

| Field | Meaning |
|---|---|
| findingId / runId | Finding and analysis-run IDs |
| sourceRevisionId | Historical source revision bound to this analysis, not the latest revision |
| filePath | Project-relative path |
| contextBefore / contextAfter | Both 20 |
| startLine / endLine | Actual first/last returned lines, one-based and clipped to file boundaries |
| highlightStartLine / highlightEndLine | Inclusive actual line range of the primary location |
| lines | Snippet lines in ascending order |
| lines[].lineNumber | Actual source line number |
| lines[].text | Original text without newline terminators; empty lines retained |
| lines[].highlighted | Whether the line belongs to the primary highlight range |

A Finding on line 62 returns lines 42–82, or only through 72 if the file ends there. The highlight remains actual line 62, not snippet-relative line 62.

Clients can use `lines.map(line => line.text).join('\n')` for editor text and startLine for displayed numbering. Convert actual lines to snippet-relative coordinates with `lineNumber - startLine + 1` when needed. This backend extension does not change frontend code.

One detail response includes both Finding and code, with no extra request or standalone /code-context endpoint. Lists do not load source and return both new fields as null. Context covers the primary location, without merging multifile occurrences. Floating-point V2 point locations highlight one line; memory-order spans may highlight several.

## Errors and boundaries

Existing project-access errors remain. SPECIALIZED_FINDING_NOT_FOUND returns 404 when the result is absent or outside the requested project/type.

The following do not fail the detail request: codeContext=null and codeContextUnavailableReason contains a code while the original Finding returns normally.

- SOURCE_REVISION_NOT_FOUND: bound revision missing or wrong ownership.
- FINDING_SOURCE_LOCATION_UNAVAILABLE: missing/invalid/reversed/out-of-file location.
- FINDING_SOURCE_FILE_NOT_FOUND: working copy/file removed; never fall back to latest code.
- FINDING_SOURCE_PATH_INVALID: absolute/traversal/escaping-symlink or otherwise invalid path.
- FINDING_SOURCE_FILE_UNREADABLE: read failure or invalid UTF-8.
- FINDING_SOURCE_FILE_TOO_LARGE: exceeds 8 MiB.
- FINDING_SOURCE_DIGEST_MISMATCH: content differs from fact.primaryLocation.sourceSha256; do not display another revision.

Endpoints neither modify results nor rescan. Source text receives no destructive path substitutions; errors expose no server absolute paths.

## Memory-order locations and snapshots

Use detail.fact.primaryLocation's relative path/span. The tool resolves referenced Scope/TU/events and never applies header line numbers to the main source. Occurrences retain multiple locations; related source-access steps retain their own positions rather than copying one across all layers.

span.end is exclusive. An end at next-line column 1 highlights through the previous line. Context remains ±20 lines around the highlight. codeContext returns the primary location; other analysis-time snippets remain in detail.occurrences[].location.context, without new endpoints.

Missing debug positions, escaping paths, or unavailable snapshots preserve formal risk/discharge verdicts and mark source gaps through source-location-unavailable and bilingual explanations. Snippets do not upgrade source candidates to formal risks. Historical records are not rewritten; rescanning obtains corrected snippets.

## Floating-point evidence-step descriptions

The same GET /api/projects/{projectId}/floating-point-findings/{findingId} returns bilingual steps in data.detail.evidenceChain.steps[]. No description endpoint is added. Top-level title/titleEn/message/messageEn is not a substitute for step wording. This extension does not change the memory-order protocol.

Floating-point results retain schemaVersion 2.0. Every new step contains:

| Field | New-output requirement |
|---|---|
| title | Nonempty Chinese title, at most 512 characters |
| titleEn | Nonempty English title, at most 512 characters |
| reason | Nonempty Chinese evidence/limitation explanation, at most 4,096 characters |
| reasonEn | Nonempty English equivalent, at most 4,096 characters |

The tool generates wording from directly referenced evidence; release tools and strict schemas together. Preserve id/kind/status/references/reasonCodes and ordering. Insufficient evidence retains partial/unknown and reasons; complete wording is not complete evidence. Example fields:

```json
{
  "title": "源码浮点比较",
  "titleEn": "Source floating-point comparison",
  "reason": "源码包含比较表达式：x == 0.1，位置为 main.cpp:1。",
  "reasonEn": "Source contains comparison x == 0.1 at main.cpp:1."
}
```

The backend imports whole raw Findings into specialized_analysis_findings.detail JSONB and passes through Chinese/English/nested references. Unavailable source context still returns original detail; only codeContext/reason follows the rules above. Access controls are unchanged.

Historical records are not backfilled. Missing evidenceChain, empty steps, or partly/entirely missing wording remains readable as originally absent, without empty strings, fixed text, or language substitution. New-producer requirements do not reject old details. Rescan to obtain wording; never silently rewrite old scans, IDs, or digests.

Download raw JSON through GET /api/projects/{projectId}/floating-point-analyses/{runId}/artifacts:download?format=json. Steps reside at findings[].evidenceChain.steps[]. Raw JSON, stored detail, and returned steps must agree. Reuse specialized report artifacts/archive registration without new archive nodes, report types, or database columns.
