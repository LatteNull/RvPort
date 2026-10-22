import type { PageResponse } from '@/types'
import type { ProjectDomainLatest } from '@/types/project'
import type {
  SpecializedAnalysis,
  SpecializedAnalysisParams,
  SpecializedAnalysisStageId,
  SpecializedFinding,
  SpecializedFindingParams
} from '@/types/project/specialized-analysis'
import type { ProjectTask } from '@/types/project/task'

import request from '../request'

function base(projectId: string, stageId: SpecializedAnalysisStageId) {
  return `/projects/${projectId}/${stageId === 'memory-order-analysis' ? 'memory-order' : 'floating-point'}-analyses`
}
export function createSpecializedAnalysis(projectId: string, stageId: SpecializedAnalysisStageId) {
  return request.post<ProjectTask>(base(projectId, stageId))
}
export function getSpecializedAnalysisLatest(
  projectId: string,
  stageId: SpecializedAnalysisStageId
) {
  return request.get<ProjectDomainLatest<SpecializedAnalysis>>(`${base(projectId, stageId)}/latest`)
}
export function getSpecializedAnalyses(
  projectId: string,
  stageId: SpecializedAnalysisStageId,
  params: SpecializedAnalysisParams
) {
  return request.get<PageResponse<SpecializedAnalysis>>(base(projectId, stageId), { params })
}
export function getSpecializedAnalysis(
  projectId: string,
  stageId: SpecializedAnalysisStageId,
  runId: string
) {
  return request.get<SpecializedAnalysis>(`${base(projectId, stageId)}/${runId}`)
}
export function getSpecializedFindings(
  projectId: string,
  stageId: SpecializedAnalysisStageId,
  runId: string,
  params: SpecializedFindingParams
) {
  return request.get<PageResponse<SpecializedFinding>>(
    `${base(projectId, stageId)}/${runId}/findings`,
    { params }
  )
}
export function getSpecializedFinding(
  projectId: string,
  stageId: SpecializedAnalysisStageId,
  findingId: string
) {
  return request.get<SpecializedFinding>(
    `/projects/${projectId}/${stageId === 'memory-order-analysis' ? 'memory-order' : 'floating-point'}-findings/${findingId}`
  )
}
export function getSpecializedArtifactDownloadUrl(
  projectId: string,
  stageId: SpecializedAnalysisStageId,
  runId: string,
  format: 'json' | 'html' | 'audit'
) {
  return `/api${base(projectId, stageId)}/${runId}/artifacts:download?format=${format}`
}
