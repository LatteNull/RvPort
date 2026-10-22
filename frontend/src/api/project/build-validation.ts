import type { PageResponse } from '@/types'
import type {
  CreateProjectBuildValidationRequest,
  ProjectBuildValidation,
  ProjectDomainLatest
} from '@/types/project'
import type { ProjectTaskStatus } from '@/types/project/task'
import type {
  ProjectTaskLogContentResponse,
  ProjectTaskLogContentType,
  ProjectTaskLogIncrementResponse
} from '@/types/project/task-log'

import request from '../request'
import type { BackendTask } from './shared'

export function getProjectBuildValidations(
  projectId: string,
  params: {
    includeStale?: boolean
    currentOnly?: boolean
    page: number
    pageSize: number
    sourceRevisionId?: string
    environmentId?: string
    buildScope?: 'BOTH' | 'SOURCE_ONLY'
    status?: ProjectTaskStatus
    createdFrom?: string
    createdTo?: string
    sortBy?: string
    sortDirection?: 'asc' | 'desc'
  }
) {
  return request.get<PageResponse<ProjectBuildValidation>>(`/projects/${projectId}/builds`, {
    params
  })
}

export function getProjectBuildValidation(buildId: string) {
  return request.get<ProjectBuildValidation>(`/builds/${buildId}`)
}

export function getProjectBuildValidationLatest(
  projectId: string,
  mode: 'SOURCE_ONLY' | 'VALIDATION'
) {
  return request.get<ProjectDomainLatest<ProjectBuildValidation>>(
    `/projects/${projectId}/builds/latest`,
    { params: { mode } }
  )
}

export function createProjectBuildValidations(
  projectId: string,
  data: CreateProjectBuildValidationRequest
) {
  return request
    .post<{ builds: ProjectBuildValidation[] }>(`/projects/${projectId}/builds`, data)
    .then((response) => response.builds)
}

export function cancelProjectBuildValidation(buildId: string) {
  return request.post<BackendTask>(`/builds/${buildId}/cancel`)
}

export function getProjectTask(taskId: string) {
  return request.get<BackendTask>(`/tasks/${taskId}`)
}

export function getProjectTaskLogContent(
  taskId: string,
  params: { lines?: number; offset?: number; type: ProjectTaskLogContentType }
) {
  const offsetKey = `${params.type}Offset`

  return request.get<ProjectTaskLogContentResponse>(`/tasks/${taskId}/log-content`, {
    params: {
      types: params.type,
      lines: params.lines,
      [offsetKey]: params.offset
    }
  })
}

export function getProjectTaskLogIncrements(
  taskId: string,
  params: { afterEventId: number; limit?: number }
) {
  return request.get<ProjectTaskLogIncrementResponse>(`/tasks/${taskId}/log-increments`, {
    params,
    suppressErrorToast: true
  })
}

export function getProjectTaskLogDownloadUrl(taskId: string, logId: string) {
  return `/api/tasks/${encodeURIComponent(taskId)}/logs/${encodeURIComponent(logId)}/download`
}
