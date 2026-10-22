export type ProjectTaskStatus =
  'PENDING' | 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED' | 'TIMEOUT'

export interface ProjectTask {
  id: string
  projectId: string
  type: string
  status: ProjectTaskStatus
  progress: number | null
  message: string | null
  createdAt: string
  queuedAt: string | null
  startedAt: string | null
  finishedAt: string | null
  errorCode: string | null
  errorMessage: string | null
  resource: Record<string, unknown>
}
