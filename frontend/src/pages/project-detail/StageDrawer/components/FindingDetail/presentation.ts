import type {
  KnowledgeBaseConclusion,
  KnowledgeBaseEvidenceChain,
  KnowledgeBaseFact,
  KnowledgeBaseOccurrence,
  ProjectKnowledgeBaseFinding,
  ProjectKnowledgeBaseFindingDetail
} from '@/types/project/knowledge-base'
export function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

export function formatEvidenceValue(value: unknown) {
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2) ?? '--'
}

export function getFindingV2(finding: ProjectKnowledgeBaseFinding) {
  const detail = finding as ProjectKnowledgeBaseFindingDetail
  const evidenceFinding = asRecord(asRecord(detail.evidence).finding)
  const fact = Object.keys(finding.fact ?? {}).length
    ? (finding.fact as KnowledgeBaseFact)
    : (asRecord(evidenceFinding.fact) as KnowledgeBaseFact)
  const conclusion = Object.keys(finding.conclusion ?? {}).length
    ? (finding.conclusion as KnowledgeBaseConclusion)
    : (asRecord(evidenceFinding.conclusion) as KnowledgeBaseConclusion)
  const occurrences = finding.occurrences?.length
    ? finding.occurrences
    : asArray<KnowledgeBaseOccurrence>(evidenceFinding.occurrences)
  const evidenceChain = Object.keys(finding.evidenceChain ?? {}).length
    ? (finding.evidenceChain as KnowledgeBaseEvidenceChain)
    : (asRecord(evidenceFinding.evidenceChain) as KnowledgeBaseEvidenceChain)
  const primaryOccurrenceId =
    detail.primaryOccurrenceId ??
    (typeof evidenceFinding.primaryOccurrenceId === 'string'
      ? evidenceFinding.primaryOccurrenceId
      : undefined)

  return { conclusion, evidenceChain, fact, occurrences, primaryOccurrenceId }
}

export function findingTitle(finding: ProjectKnowledgeBaseFinding) {
  return getFindingV2(finding).conclusion.title ?? finding.title ?? finding.ruleId
}

export function findingLocation(finding: ProjectKnowledgeBaseFinding) {
  const location = getFindingV2(finding).fact.primaryLocation
  const file = location?.file ?? finding.filePath
  const start = location?.span?.start?.line ?? finding.lineStart
  const end = location?.span?.end?.line ?? finding.lineEnd
  return { end, file, start }
}

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : []
}
