import { useQuery } from '@tanstack/react-query'

import { getProjectOverview } from '@/api/project/projects'

import { projectQueryKeys } from './queryKeys'

export function useProjectOverview(projectId?: string, enabled = true) {
  return useQuery({
    queryKey: projectQueryKeys.overview(projectId),
    queryFn: () => getProjectOverview(projectId ?? ''),
    enabled: Boolean(projectId) && enabled,
    refetchOnMount: false,
    refetchOnReconnect: false,
    refetchOnWindowFocus: false,
    staleTime: 30_000
  })
}
