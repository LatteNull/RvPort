import type { PageResponse } from '@/types'
import type {
  ProjectMigrationInputAutoMergeConfig,
  ProjectMigrationInputAutoMergeResponse,
  ProjectMigrationInputDetail,
  ProjectMigrationInputImportRequest,
  ProjectMigrationInputImportResponse,
  ProjectMigrationInputItem,
  ProjectMigrationInputListParams,
  UpdateProjectMigrationInputRequest
} from '@/types/project/migration-input'

import request from '../request'

function migrationInputsPath(projectId: string, sourceRevisionId: string) {
  return `/projects/${projectId}/source-revisions/${sourceRevisionId}/migration-inputs`
}

export function getProjectMigrationInputs(
  projectId: string,
  sourceRevisionId: string,
  params: ProjectMigrationInputListParams
) {
  return request.get<PageResponse<ProjectMigrationInputItem>>(
    migrationInputsPath(projectId, sourceRevisionId),
    { params }
  )
}

export function importProjectMigrationInputs(
  projectId: string,
  sourceRevisionId: string,
  data: ProjectMigrationInputImportRequest
) {
  return request.post<ProjectMigrationInputImportResponse>(
    `${migrationInputsPath(projectId, sourceRevisionId)}:import`,
    data
  )
}

export function autoMergeProjectMigrationInputs(
  projectId: string,
  sourceRevisionId: string,
  data: ProjectMigrationInputAutoMergeConfig
) {
  return request.post<ProjectMigrationInputAutoMergeResponse>(
    `${migrationInputsPath(projectId, sourceRevisionId)}:auto-merge`,
    data
  )
}

export function getProjectMigrationInput(migrationInputId: string) {
  return request.get<ProjectMigrationInputDetail>(`/migration-inputs/${migrationInputId}`)
}

export function updateProjectMigrationInput(
  migrationInputId: string,
  data: UpdateProjectMigrationInputRequest
) {
  return request.patch<ProjectMigrationInputItem>(`/migration-inputs/${migrationInputId}`, data)
}
