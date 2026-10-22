import { useMemo } from 'react'

import type {
  ProjectBuildValidation,
  ProjectRuntimeEnvironmentSummary,
  ProjectSourceArtifact
} from '@/types/project'
import type { ProjectDependencyAnalysis } from '@/types/project/dependency-analysis'
import type { ProjectTaskStatus } from '@/types/project/task'

import { useProjectOverviewData } from '../ProjectOverviewContext'

const terminalTaskStatuses = new Set<ProjectTaskStatus>([
  'SUCCEEDED',
  'FAILED',
  'CANCELLED',
  'TIMEOUT'
])

export function isTerminalBuildReadinessStatus(status?: ProjectTaskStatus) {
  return Boolean(status && terminalTaskStatuses.has(status))
}

export function getSourceDisplayName(source: ProjectSourceArtifact | null | undefined) {
  if (!source) return null
  if (source.type === 'ARCHIVE') return source.fileName ?? null

  const repositoryUrl = source.repositoryUrl?.replace(/[\\/]+$/, '')
  const repositoryName = repositoryUrl?.split(/[/:]/).filter(Boolean).at(-1)
  return repositoryName?.replace(/\.git$/i, '') || null
}

export function isCurrentBuildReadinessRecord(
  record:
    | Pick<
        ProjectBuildValidation,
        'sourceRevisionId' | 'currentRuntimeEnvironment' | 'environmentConfigVersion'
      >
    | Pick<
        ProjectDependencyAnalysis,
        'sourceRevisionId' | 'currentRuntimeEnvironment' | 'environmentConfigVersion'
      >,
  sourceRevisionId: string | null | undefined,
  runtimeEnvironmentVersion: number | undefined
) {
  return (
    Boolean(sourceRevisionId) &&
    record.sourceRevisionId === sourceRevisionId &&
    record.currentRuntimeEnvironment &&
    record.environmentConfigVersion === runtimeEnvironmentVersion
  )
}

export interface BuildReadinessContext {
  activeSourceRevisionId: string | null
  activeSourceName: string | null
  activeSourceRepositoryUrl: string | null
  sourceEnvironment: ProjectRuntimeEnvironmentSummary | null
  targetEnvironment: ProjectRuntimeEnvironmentSummary | null
  runtimeEnvironmentReady: boolean
  runtimeEnvironmentVersion: number | undefined
}

export function useBuildReadinessContext(projectId: string | undefined) {
  const overviewQuery = useProjectOverviewData(projectId)
  const currentContext = overviewQuery.data?.currentContext
  const runtimeEnvironments = currentContext?.runtimeEnvironments
  const activeSourceRevisionId = currentContext?.activeSourceRevision?.id
  const context = useMemo<BuildReadinessContext>(() => {
    const sourceEnvironment = runtimeEnvironments?.sourceEnvironment ?? null
    const targetEnvironment = runtimeEnvironments?.targetEnvironment ?? null
    const runtimeEnvironmentVersion = runtimeEnvironments?.version
    return {
      activeSourceRevisionId: activeSourceRevisionId ?? null,
      activeSourceName: getSourceDisplayName(currentContext?.activeSourceRevision),
      activeSourceRepositoryUrl:
        currentContext?.activeSourceRevision?.type === 'GIT'
          ? (currentContext.activeSourceRevision.repositoryUrl ?? null)
          : null,
      sourceEnvironment,
      targetEnvironment,
      runtimeEnvironmentReady: Boolean(runtimeEnvironments?.ready),
      runtimeEnvironmentVersion
    }
  }, [activeSourceRevisionId, currentContext?.activeSourceRevision, runtimeEnvironments])

  return {
    context,
    hasData: Boolean(overviewQuery.data),
    isError: overviewQuery.isError,
    isLoading: overviewQuery.isLoading,
    refetch: () => Promise.all([overviewQuery.refetch()])
  }
}
