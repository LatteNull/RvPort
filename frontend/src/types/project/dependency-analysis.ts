import type { ProjectMigrationInputStatus } from './migration-input'
import type { ProjectTaskStatus } from './task'

export interface ProjectDependencyAnalysis {
  id: string
  projectId: string
  taskId: string
  sourceRevisionId: string
  sourceBuildRunId: string
  targetEnvironmentId: string
  environmentConfigVersion: number | null
  currentEnvironmentConfigVersion: number
  currentRuntimeEnvironment: boolean
  currentSourceRevision?: boolean
  staleReasons?: string[]
  status: ProjectTaskStatus
  summary: Record<string, unknown>
  warnings: unknown
  startedAt: string | null
  finishedAt: string | null
  createdAt: string
}

export interface CreateProjectDependencyAnalysisRequest {
  sourceRevisionId?: string
}

export interface ProjectDependencyAnalysisListParams {
  includeStale?: boolean
  currentOnly?: boolean
  page: number
  pageSize: number
  sourceRevisionId?: string
  status?: ProjectTaskStatus
  riskLevel?: string
  createdFrom?: string
  createdTo?: string
  sortBy?: string
  sortDirection?: 'asc' | 'desc'
}

export interface ProjectDependencyAnalysisResultListParams {
  page: number
  pageSize: number
  dependencyType?: string
  targetMatchStatus?: string
  riskLevel?: string
  keyword?: string
  sortBy?: string
  sortDirection?: 'asc' | 'desc'
}

export interface ProjectDependencyAnalysisResult {
  id: string
  dependencyType: string
  dependencyName: string
  dependencyVersion: string | null
  sourceProviderPackage: string | null
  sourceProviderVersion: string | null
  sourceDetectedVersion: string | null
  targetProviderPackage: string | null
  targetProviderVersion: string | null
  targetDetectedVersion: string | null
  providerVersionStatus: string | null
  versionEvidenceConfidence: string | null
  targetMatchStatus: string
  riskLevel: string
  locationLabel: string | null
  recommendation: string | null
  confidence: string
  evidence: Record<string, unknown>
  createdAt: string
  migrationInputRefId?: string | null
  migrationInputStatus?: ProjectMigrationInputStatus | null
  confirmedForNextReport?: boolean
  includedInLatestReport?: boolean
  latestReportId?: string | null
}

export interface ProjectDependencyAnalysisArtifact {
  id: string
  artifactType: string
  contentType: string
  sizeBytes: number | null
  sha256: string | null
  summary: Record<string, unknown>
  createdAt: string
}

export interface ProjectDependencyAnalysisArtifactDetail {
  artifact: ProjectDependencyAnalysisArtifact
  content: unknown
}

export interface ProjectDependencyAutoFixCandidateListParams {
  page: number
  pageSize: number
  dependencyType?: string
  targetMatchStatus?: string
  riskLevel?: string
  defaultSelected?: boolean
  selectable?: boolean
  keyword?: string
  sortBy?: string
  sortDirection?: 'asc' | 'desc'
}

export interface ProjectDependencyAutoFixCandidate {
  resultItemId: string
  dependencyType: string
  dependencyName: string
  dependencyVersion: string | null
  riskLevel: string
  targetMatchStatus: string
  sourceProviderPackage: string | null
  sourceProviderVersion: string | null
  targetProviderPackage: string | null
  targetProviderVersion: string | null
  installPackageName: string
  installVersionConstraint: string | null
  defaultSelected: boolean
  selectable: boolean
  reason: string
}

export interface CreateProjectDependencyAutoFixRequest {
  resultItemIds: string[]
  rerunDependencyAnalysis?: boolean
}

export interface CreateProjectDependencyAutoFixResponse {
  autoFixRunId: string
  taskId: string
  selectedCount: number
}
