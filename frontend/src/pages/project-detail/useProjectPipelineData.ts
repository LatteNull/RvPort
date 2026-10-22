import { useCallback, useMemo } from 'react'

import { projectStageConfig } from '@/config/project-status'

import { useProjectOverview } from './useProjectOverview'
import { getCurrentWorkflowStageId, getWorkflowStageTitle } from './Workflow/stageData'

export function useProjectPipelineData(projectId?: string) {
  const {
    data: overview,
    isError,
    isLoading,
    isFetching,
    refetch: refetchOverview
  } = useProjectOverview(projectId)
  const refetch = useCallback(async () => {
    await refetchOverview()
  }, [refetchOverview])

  const recommendedStageId = overview
    ? getCurrentWorkflowStageId(overview.workflow.recommendedStageId, overview.workflow.stages)
    : undefined

  const workflowStatus = useMemo(
    () =>
      overview
        ? {
            projectId: overview.project.id,
            currentStageId: recommendedStageId ?? '',
            stages: overview.workflow.stages,
            activeEdgeIds: [],
            updatedAt: overview.project.updatedAt ?? overview.project.createdAt
          }
        : undefined,
    [overview, recommendedStageId]
  )

  const currentStageTitle =
    getWorkflowStageTitle(recommendedStageId ?? undefined) ??
    (overview ? projectStageConfig[overview.project.stage].label : undefined) ??
    ''

  return {
    overview,
    isFetching,
    workflowStatus,
    currentStageTitle,
    isError,
    isLoading,
    refetch
  }
}
