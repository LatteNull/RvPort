import type {
  ProjectTaskLogContentType,
  ProjectTaskLogIncrementResponse
} from '@/types/project/task-log'

export const TASK_LOG_CONTENT_TYPES: ProjectTaskLogContentType[] = ['merged', 'stdout', 'stderr']

export const EMPTY_TASK_LOG_BUFFERS: Record<ProjectTaskLogContentType, string> = {
  merged: '',
  stdout: '',
  stderr: ''
}

export interface TaskLogStreamState {
  buffers: Record<ProjectTaskLogContentType, string>
  cursor: number
  truncated: boolean
}

interface TaskLogBufferLimits {
  maxCharacters: number
  maxLines: number
}

export const DEFAULT_TASK_LOG_BUFFER_LIMITS: TaskLogBufferLimits = {
  maxCharacters: 4 * 1024 * 1024,
  maxLines: 20_000
}

export function createTaskLogStreamState(): TaskLogStreamState {
  return {
    buffers: { ...EMPTY_TASK_LOG_BUFFERS },
    cursor: 0,
    truncated: false
  }
}

const TERMINAL_TASK_LOG_STATUSES = new Set(['SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT'])

export function isTerminalTaskLogStatus(status?: string) {
  return Boolean(status && TERMINAL_TASK_LOG_STATUSES.has(status))
}

function trimBuffer(content: string, limits: TaskLogBufferLimits) {
  let next = content
  let truncated = false

  if (next.length > limits.maxCharacters) {
    const cutoff = next.length - limits.maxCharacters
    const firstCompleteLine = next.indexOf('\n', cutoff)
    next = next.slice(firstCompleteLine >= 0 ? firstCompleteLine + 1 : cutoff)
    truncated = true
  }

  const lines = next.split('\n')
  if (lines.length > limits.maxLines) {
    next = lines.slice(lines.length - limits.maxLines).join('\n')
    truncated = true
  }

  return { content: next, truncated }
}

export function appendTaskLogIncrement(
  state: TaskLogStreamState,
  response: ProjectTaskLogIncrementResponse,
  limits: TaskLogBufferLimits = DEFAULT_TASK_LOG_BUFFER_LIMITS
): TaskLogStreamState {
  const buffers = { ...state.buffers }
  let truncated = state.truncated

  for (const type of TASK_LOG_CONTENT_TYPES) {
    const trimmed = trimBuffer(`${buffers[type]}${response.logs[type].content}`, limits)
    buffers[type] = trimmed.content
    truncated ||= trimmed.truncated
  }

  return {
    buffers,
    cursor: response.latestEventId,
    truncated
  }
}
