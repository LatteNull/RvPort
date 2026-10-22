import { useQuery } from '@tanstack/react-query'

import { getProjectOptimizationCycleLatest } from '@/api/project/optimization-cycle'
import { getProjectStageReadiness } from '@/api/project/workflow'

import { projectQueryKeys } from '../../queryKeys'

export function useOptimizationCycleDrawer(projectId: string | undefined, enabled: boolean) {
  const readinessQuery = useQuery({
    queryKey: projectQueryKeys.readiness(projectId, 'optimize'),
    queryFn: () => getProjectStageReadiness(projectId ?? '', 'optimize'),
    enabled: enabled && Boolean(projectId)
  })
  const latestQuery = useQuery({
    queryKey: projectQueryKeys.optimizationLatest(projectId),
    queryFn: () => getProjectOptimizationCycleLatest(projectId ?? ''),
    enabled: enabled && Boolean(projectId)
  })
  const activeSourcePrerequisite = readinessQuery.data?.prerequisites.find(
    (item) => item.key === 'ACTIVE_SOURCE'
  )

  return {
    hasData: Boolean(readinessQuery.data && latestQuery.data),
    activeSourcePrerequisite,
    currentCycle:
      latestQuery.data?.freshness === 'CURRENT' ? (latestQuery.data.result ?? null) : null,
    freshness: latestQuery.data?.freshness,
    isError: readinessQuery.isError || latestQuery.isError,
    isFetching: readinessQuery.isFetching || latestQuery.isFetching,
    isLoading: readinessQuery.isLoading || latestQuery.isLoading,
    ready: activeSourcePrerequisite?.status === 'SATISFIED',
    refetch: () => Promise.all([readinessQuery.refetch(), latestQuery.refetch()])
  }
}
