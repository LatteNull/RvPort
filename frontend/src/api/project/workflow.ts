import type {
  ProjectStageDetail,
  ProjectStageReadiness,
  ProjectWorkflowStatus
} from '@/types/project'

import request from '../request'

export function getProjectWorkflowStatus(projectId: string) {
  return request.get<ProjectWorkflowStatus>(`/projects/${projectId}/workflow/status`)
}

export function getProjectStageReadiness(projectId: string, stageId: string) {
  return request.get<ProjectStageReadiness>(`/projects/${projectId}/readiness`, {
    params: { stageId }
  })
}

export function getProjectStageDetail<TData = unknown>(projectId: string, stageId: string) {
  return request.get<ProjectStageDetail<TData>>(`/projects/${projectId}/workflow/stages/${stageId}`)
}
