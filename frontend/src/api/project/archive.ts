import type { PageResponse } from '@/types'
import type {
  ProjectArchive,
  ProjectArchiveCreateResponse,
  ProjectArchiveListParams,
  ProjectDomainLatest
} from '@/types/project'

import request from '../request'

export function getProjectArchiveLatest(projectId: string) {
  return request.get<ProjectDomainLatest<ProjectArchive>>(`/projects/${projectId}/archives/latest`)
}

export function createProjectArchive(projectId: string) {
  return request.post<ProjectArchiveCreateResponse>(`/projects/${projectId}/archives`)
}

export function getProjectArchives(projectId: string, params: ProjectArchiveListParams) {
  return request.get<PageResponse<ProjectArchive>>(`/projects/${projectId}/archives`, { params })
}

export function getProjectArchive(archiveId: string) {
  return request.get<ProjectArchive>(`/archives/${archiveId}`)
}

export function getProjectArchiveDownloadUrl(archiveId: string) {
  return `/api/archives/${archiveId}/download`
}

export function getProjectArchiveItemDownloadUrl(
  archiveId: string,
  itemId: string,
  format: string
) {
  return `/api/archives/${archiveId}/items/${itemId}?format=${encodeURIComponent(format)}`
}
