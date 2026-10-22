export type WorkerInstanceStatus = 'ONLINE' | 'OFFLINE'

export interface WorkerInstance {
  activeConcurrency: number
  activeTaskCount: number
  appVersion: string
  concurrencyLimit: number
  createdAt: string
  hostname: string
  instanceId: string
  lastHeartbeatAt: string
  processId: number
  startedAt: string
  status: WorkerInstanceStatus
  updatedAt: string
}

export interface WorkerTask {
  message: string | null
  progress: number
  projectId: string
  projectName: string
  startedAt: string
  status: 'PENDING' | 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED' | 'TIMEOUT'
  taskId: string
  type: string
}

export interface WorkerInstanceDetail {
  runningTasks: WorkerTask[]
  worker: WorkerInstance
}

export interface AdminWorkerListParams {
  hasRunningTasks?: boolean
  hostname?: string
  instanceId?: string
  page: number
  pageSize: number
  sortBy?: WorkerSortField
  sortDirection?: 'asc' | 'desc'
  status?: WorkerInstanceStatus
}

export type WorkerSortField =
  | 'instanceId'
  | 'hostname'
  | 'status'
  | 'concurrencyLimit'
  | 'activeConcurrency'
  | 'activeTaskCount'
  | 'startedAt'
  | 'updatedAt'
  | 'lastHeartbeatAt'
