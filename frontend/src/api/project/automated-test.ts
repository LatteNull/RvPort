import type { PageResponse } from '@/types'
import type {
  CreateProjectAutomatedTestRequest,
  ProjectAutomatedTest,
  ProjectDomainLatest,
  ProjectTestComparison
} from '@/types/project'

import request from '../request'
import type { BackendTask } from './shared'

export function getProjectAutomatedTests(
  projectId: string,
  params: {
    page: number
    pageSize: number
    sourceRevisionId?: string
    sortBy?: 'createdAt' | 'startedAt'
    sortDirection?: 'asc' | 'desc'
  }
) {
  return request.get<PageResponse<ProjectAutomatedTest>>(`/projects/${projectId}/tests`, { params })
}

export function getProjectAutomatedTestLatest(projectId: string) {
  return request.get<ProjectDomainLatest<ProjectAutomatedTest>>(
    `/projects/${projectId}/automated-tests/latest`
  )
}

export function createProjectAutomatedTest(
  projectId: string,
  data: CreateProjectAutomatedTestRequest
) {
  return request.post<BackendTask>(`/projects/${projectId}/tests`, data)
}

export function cancelProjectAutomatedTest(testRunId: string) {
  return request.post<BackendTask>(`/tests/${testRunId}/cancel`)
}

export function getProjectTestComparisons(
  projectId: string,
  params: { page: number; pageSize: number; testBatchId?: string }
) {
  return request.get<PageResponse<ProjectTestComparison>>(
    `/projects/${projectId}/test-comparisons`,
    {
      params
    }
  )
}
