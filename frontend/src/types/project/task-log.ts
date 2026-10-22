export type ProjectTaskLogContentType = 'merged' | 'stdout' | 'stderr'

export interface ProjectTaskLogContent {
  type: ProjectTaskLogContentType
  logId: string | null
  offset: number
  lines: number
  returnedLines: number
  totalLines: number
  hasMore: boolean
  content: string
}

export interface ProjectTaskLogContentResponse {
  logs: Partial<Record<ProjectTaskLogContentType, ProjectTaskLogContent>>
}

export interface ProjectTaskLogIncrement {
  content: string
  returnedEvents: number
}

export interface ProjectTaskLogIncrementResponse {
  taskId: string
  fromEventId: number | null
  latestEventId: number
  hasMore: boolean
  logs: Record<ProjectTaskLogContentType, ProjectTaskLogIncrement>
}

export interface ProjectTaskLogUpdatedEvent {
  taskId: string
  latestEventId: number
  status: ProjectTaskStatus
}

export interface ProjectTaskLogCompletedEvent extends ProjectTaskLogUpdatedEvent {
  message?: string | null
}

export type ProjectTaskLogConnectionStatus =
  'idle' | 'connecting' | 'connected' | 'reconnecting' | 'completed'
import type { ProjectTaskStatus } from './task'
