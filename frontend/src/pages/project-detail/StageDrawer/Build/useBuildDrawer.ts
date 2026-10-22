import { useQuery } from '@tanstack/react-query'

import {
  cancelProjectBuildValidation,
  createProjectBuildValidations,
  getProjectBuildValidationLatest
} from '@/api/project/build-validation'
import { getProjectStageReadiness } from '@/api/project/workflow'
import { useSessionMutation } from '@/hooks/useSessionMutation'
import type { CreateProjectBuildValidationRequest } from '@/types/project'
import type { ProjectTaskStatus } from '@/types/project/task'
import { feedback } from '@/utils/feedback'

import { projectQueryKeys } from '../../queryKeys'
import { useBuildReadinessContext } from '../buildReadinessContext'

const terminalTaskStatuses: ProjectTaskStatus[] = ['SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT']

export const projectBuildValidationQueryKey = (projectId: string | undefined) =>
  ['project-build-validations', projectId, 'VALIDATION'] as const

export function isTerminalTaskStatus(status: ProjectTaskStatus | undefined) {
  return status ? terminalTaskStatuses.includes(status) : false
}

export function useBuildDrawer(projectId: string | undefined, enabled: boolean) {
  const contextQuery = useBuildReadinessContext(projectId)
  const readinessQuery = useQuery({
    queryKey: projectQueryKeys.readiness(projectId, 'build'),
    queryFn: () => getProjectStageReadiness(projectId ?? '', 'build'),
    enabled: enabled && Boolean(projectId)
  })
  const latestQuery = useQuery({
    queryKey: [...projectBuildValidationQueryKey(projectId), 'latest'],
    queryFn: () => getProjectBuildValidationLatest(projectId ?? '', 'VALIDATION'),
    enabled: enabled && Boolean(projectId)
  })
  const sourceRevisionId = readinessQuery.data?.context.sourceRevisionId ?? undefined
  const generationPrerequisites = ['ACTIVE_SOURCE', 'SOURCE_ENVIRONMENT', 'TARGET_ENVIRONMENT'].map(
    (key) => readinessQuery.data?.prerequisites.find((item) => item.key === key)
  )
  const buildReady = generationPrerequisites.every(
    (prerequisite) => prerequisite?.status === 'SATISFIED'
  )
  const latestBuildResult =
    latestQuery.data?.freshness === 'CURRENT' ? latestQuery.data.result : null
  const latestBuild =
    latestBuildResult && latestQuery.data?.execution
      ? { ...latestBuildResult, status: latestQuery.data.execution.status }
      : latestBuildResult
  const buildMutation = useSessionMutation({
    sessionKey: `build:${projectId}`,
    active: enabled,
    mutationFn: (data: CreateProjectBuildValidationRequest) =>
      createProjectBuildValidations(projectId ?? '', {
        ...data,
        buildScope: 'BOTH',
        sourceRevisionId
      }),
    onSuccess: () => {
      feedback.success('构建任务已创建')
    }
  })
  const cancelMutation = useSessionMutation({
    sessionKey: `cancel-build:${projectId}`,
    active: enabled,
    mutationFn: cancelProjectBuildValidation,
    onSuccess: () => {
      feedback.success('构建取消请求已提交')
    }
  })

  return {
    buildReady,
    hasData: Boolean(contextQuery.hasData && readinessQuery.data && latestQuery.data),
    buildMutation,
    cancelMutation,
    context: contextQuery.context,
    generationPrerequisites,
    isError: enabled && (contextQuery.isError || readinessQuery.isError || latestQuery.isError),
    isLoading:
      enabled && (contextQuery.isLoading || readinessQuery.isLoading || latestQuery.isLoading),
    latestBuild,
    latestFreshness: latestQuery.data?.freshness,
    refetch: () =>
      Promise.all([contextQuery.refetch(), readinessQuery.refetch(), latestQuery.refetch()]),
    sourceRevisionId
  }
}
