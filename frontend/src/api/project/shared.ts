export interface BackendTask {
  id: string
  projectId: string
  type: string
  status: 'PENDING' | 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED' | 'TIMEOUT'
  progress: number
  message: string | null
  createdAt: string
  queuedAt: string | null
  startedAt: string | null
  finishedAt: string | null
  errorCode: string | null
  errorMessage: string | null
  resource: {
    environmentRole?: string
    id: string
    mode?: string
    type: string
  }
}
