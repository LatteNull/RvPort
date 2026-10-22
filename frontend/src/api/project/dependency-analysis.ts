import type { PageResponse } from '@/types'
import type { ProjectDomainLatest } from '@/types/project'
import type {
  CreateProjectDependencyAnalysisRequest,
  CreateProjectDependencyAutoFixRequest,
  CreateProjectDependencyAutoFixResponse,
  ProjectDependencyAnalysis,
  ProjectDependencyAnalysisArtifact,
  ProjectDependencyAnalysisArtifactDetail,
  ProjectDependencyAnalysisListParams,
  ProjectDependencyAnalysisResult,
  ProjectDependencyAnalysisResultListParams,
  ProjectDependencyAutoFixCandidate,
  ProjectDependencyAutoFixCandidateListParams
} from '@/types/project/dependency-analysis'

import request from '../request'

export function createProjectDependencyAnalysis(
  projectId: string,
  data: CreateProjectDependencyAnalysisRequest = {}
) {
  return request.post<{
    analysisRunId: string
    taskId: string
    sourceRevisionId: string
    sourceBuildRunId: string
  }>(`/projects/${projectId}/dependency-analyses`, data)
}

export function getProjectDependencyAnalyses(
  projectId: string,
  params: ProjectDependencyAnalysisListParams
) {
  return request.get<PageResponse<ProjectDependencyAnalysis>>(
    `/projects/${projectId}/dependency-analyses`,
    { params }
  )
}

export function getProjectDependencyAnalysisLatest(projectId: string) {
  return request.get<ProjectDomainLatest<ProjectDependencyAnalysis>>(
    `/projects/${projectId}/dependency-analyses/latest`
  )
}

export function getProjectDependencyAnalysis(analysisId: string) {
  return request.get<ProjectDependencyAnalysis>(`/dependency-analyses/${analysisId}`)
}

export function getProjectDependencyAnalysisResults(
  analysisId: string,
  params: ProjectDependencyAnalysisResultListParams
) {
  return request.get<PageResponse<ProjectDependencyAnalysisResult>>(
    `/dependency-analyses/${analysisId}/results`,
    { params }
  )
}

export function getProjectDependencyAnalysisResult(resultId: string) {
  return request.get<ProjectDependencyAnalysisResult>(`/dependency-analysis-results/${resultId}`)
}

export function getProjectDependencyAnalysisArtifacts(analysisId: string) {
  return request.get<ProjectDependencyAnalysisArtifact[]>(
    `/dependency-analyses/${analysisId}/artifacts`
  )
}

export function getProjectDependencyAnalysisArtifact(analysisId: string, artifactType: string) {
  return request.get<ProjectDependencyAnalysisArtifactDetail>(
    `/dependency-analyses/${analysisId}/artifacts/${artifactType}`
  )
}

export function getProjectDependencyAutoFixCandidates(
  analysisId: string,
  params: ProjectDependencyAutoFixCandidateListParams
) {
  return request.get<PageResponse<ProjectDependencyAutoFixCandidate>>(
    `/dependency-analyses/${analysisId}/auto-fix-candidates`,
    { params }
  )
}

export function createProjectDependencyAutoFix(
  analysisId: string,
  data: CreateProjectDependencyAutoFixRequest
) {
  return request.post<CreateProjectDependencyAutoFixResponse>(
    `/dependency-analyses/${analysisId}/auto-fixes`,
    data
  )
}
