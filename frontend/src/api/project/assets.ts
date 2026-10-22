import type {
  ProjectSourceArtifact,
  UpdateProjectSourceFromGitRequest,
  UploadProjectSourceArtifactRequest
} from '@/types/project'

import request, { UPLOAD_REQUEST_TIMEOUT_MS } from '../request'
import { type BackendTask } from './shared'

export interface BackendSourceRevision {
  id: string
  projectId: string
  revisionType: 'ARCHIVE' | 'GIT'
  versionLabel: string | null
  sourceUri: string | null
  gitUrl: string | null
  gitBranch: string | null
  gitCommit: string | null
  versionNote: string | null
  active: boolean
  createdAt: string
  createdBy: string
}

interface BackendSourceArchiveResponse {
  sourceRevision: BackendSourceRevision
  sourceImport: unknown
}

export function toProjectSourceArtifact(source: BackendSourceRevision): ProjectSourceArtifact {
  return {
    active: source.active,
    id: source.id,
    type: source.revisionType,
    version: source.versionLabel ?? source.gitCommit ?? source.gitBranch ?? source.id,
    versionNote: source.versionNote ?? '',
    updatedAt: source.createdAt,
    fileName:
      source.revisionType === 'ARCHIVE'
        ? (source.sourceUri?.split('/').filter(Boolean).at(-1) ?? undefined)
        : undefined,
    repositoryUrl: source.revisionType === 'GIT' ? (source.gitUrl ?? undefined) : undefined,
    branch: source.revisionType === 'GIT' ? (source.gitBranch ?? undefined) : undefined,
    ref: source.revisionType === 'GIT' ? (source.gitCommit ?? undefined) : undefined
  }
}

export function uploadProjectSourceArtifact(
  projectId: string,
  { file, versionNote }: UploadProjectSourceArtifactRequest
) {
  const data = new FormData()
  data.append('file', file)
  if (versionNote) data.append('versionNote', versionNote)
  data.append('activate', 'true')
  return request
    .post<BackendSourceArchiveResponse>(`/projects/${projectId}/sources/archive`, data, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: UPLOAD_REQUEST_TIMEOUT_MS
    })
    .then((response) => toProjectSourceArtifact(response.sourceRevision))
}

export function updateProjectSourceFromGit(
  projectId: string,
  data: UpdateProjectSourceFromGitRequest
) {
  return request.post<BackendTask>(`/projects/${projectId}/sources/git-sync`, {
    gitUrl: data.repositoryUrl,
    gitBranch: data.ref,
    username: data.username,
    token: data.accessToken,
    credentialKind: data.accessToken ? 'GIT_TOKEN' : undefined,
    activate: true
  })
}
