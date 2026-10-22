import { createContext, useContext } from 'react'

import type { ProjectOverview } from '@/types/project'

export interface ProjectOverviewState {
  projectId?: string
  data?: ProjectOverview
  isError: boolean
  isLoading: boolean
  isFetching: boolean
  refetch: () => Promise<unknown>
}

export const ProjectOverviewContext = createContext<ProjectOverviewState | null>(null)

export function useProjectOverviewData(projectId?: string) {
  const state = useContext(ProjectOverviewContext)
  if (!state || state.projectId !== projectId)
    throw new Error('阶段必须在所属项目的 overview 数据边界内使用')
  return state
}
