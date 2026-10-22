import type { PageResponse } from '@/types'
import type {
  ProjectDomainLatest,
  ProjectOptimizationCycle,
  ProjectOptimizationCycleListParams
} from '@/types/project'

import request from '../request'

export function getProjectOptimizationCycleLatest(projectId: string) {
  return request.get<ProjectDomainLatest<ProjectOptimizationCycle>>(
    `/projects/${projectId}/optimization-cycles/latest`
  )
}

export function getProjectOptimizationCycles(
  projectId: string,
  params: ProjectOptimizationCycleListParams
) {
  return request.get<PageResponse<ProjectOptimizationCycle>>(
    `/projects/${projectId}/optimization/cycles`,
    { params }
  )
}

export function getProjectOptimizationCycle(projectId: string, cycleId: string) {
  return request.get<ProjectOptimizationCycle>(
    `/projects/${projectId}/optimization/cycles/${cycleId}`
  )
}
