import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { useMutation } from '@tanstack/react-query'

import { getProjectTaskLogIncrements } from '@/api/project/build-validation'
import {
  getAuthGeneration,
  isAuthGenerationCurrent,
  SessionChangedError,
  subscribeAuthSession
} from '@/store/authSession'
import type {
  ProjectTaskLogCompletedEvent,
  ProjectTaskLogConnectionStatus,
  ProjectTaskLogUpdatedEvent
} from '@/types/project/task-log'

import {
  appendTaskLogIncrement,
  createTaskLogStreamState,
  type TaskLogStreamState
} from '../utils/taskLogStream'

const RECONNECT_INITIAL_DELAY_MS = 1_000
const RECONNECT_MAX_DELAY_MS = 15_000
const INCREMENT_RETRY_DELAY_MS = 1_500

interface UseTaskLogStreamOptions {
  enabled: boolean
  taskId?: string
  onCompleted?: (event: ProjectTaskLogCompletedEvent) => void
}
export interface TaskLogStreamResult extends TaskLogStreamState {
  completed: boolean
  connectionStatus: ProjectTaskLogConnectionStatus
  error: Error | null
  isFetching: boolean
  retry: () => void
}
function initialState() {
  return {
    ...createTaskLogStreamState(),
    completed: false,
    connectionStatus: 'idle' as ProjectTaskLogConnectionStatus,
    error: null as Error | null,
    isFetching: false
  }
}
function parseEvent<T>(event: Event): T | null {
  try {
    return JSON.parse((event as MessageEvent<string>).data) as T
  } catch {
    return null
  }
}

export function useTaskLogStream({
  enabled,
  taskId,
  onCompleted
}: UseTaskLogStreamOptions): TaskLogStreamResult {
  const generation = useSyncExternalStore(
    subscribeAuthSession,
    getAuthGeneration,
    getAuthGeneration
  )
  const [session, setSession] = useState(() => ({ generation, taskId, state: initialState() }))
  const retryRef = useRef<(() => void) | undefined>(undefined)
  const onCompletedRef = useRef(onCompleted)
  const { mutateAsync } = useMutation({
    mutationFn: ({
      id,
      cursor,
      generation
    }: {
      id: string
      cursor: number
      generation: number
    }) => {
      if (!isAuthGenerationCurrent(generation)) throw new SessionChangedError()
      return getProjectTaskLogIncrements(id, { afterEventId: cursor, limit: 500 })
    }
  })
  useEffect(() => {
    onCompletedRef.current = onCompleted
  }, [onCompleted])
  const retry = useCallback(() => retryRef.current?.(), [])

  useEffect(() => {
    // 每个 effect 拥有游标、锁与定时器；旧 finally 只能清理自己。
    let disposed = false
    const isCurrent = () => !disposed && isAuthGenerationCurrent(generation)
    let cursor = 0
    let targetCursor = 0
    let draining = false
    let pendingDrain = false
    let completedEvent: ProjectTaskLogCompletedEvent | null = null
    let completionNotified = false
    let retryTimer: number | undefined
    let reconnectTimer: number | undefined
    let eventSource: EventSource | undefined
    let reconnectDelay = RECONNECT_INITIAL_DELAY_MS
    let state = initialState()
    const publish = (patch: Partial<typeof state>) => {
      if (!isCurrent()) return
      state = { ...state, ...patch }
      setSession({ generation, taskId, state })
    }
    const clearRetry = () => {
      if (retryTimer !== undefined) window.clearTimeout(retryTimer)
      retryTimer = undefined
    }
    const closeSource = () => {
      if (eventSource) {
        eventSource.onopen = null
        eventSource.onerror = null
        eventSource.close()
        eventSource = undefined
      }
    }
    const drain = async () => {
      if (!isCurrent() || !enabled || !taskId || completionNotified) return
      if (draining) {
        pendingDrain = true
        return
      }
      clearRetry()
      draining = true
      pendingDrain = false
      publish({ error: null, isFetching: true })
      try {
        let keepReading = true
        while (keepReading && isCurrent()) {
          const previousCursor = cursor
          const response = await mutateAsync({ id: taskId, cursor, generation })
          if (!isCurrent()) return
          cursor = response.latestEventId
          publish(appendTaskLogIncrement(state, response))
          keepReading =
            response.hasMore || pendingDrain || (cursor < targetCursor && cursor > previousCursor)
          pendingDrain = false
        }
        if (
          isCurrent() &&
          completedEvent &&
          cursor >= completedEvent.latestEventId &&
          !completionNotified
        ) {
          completionNotified = true
          publish({ completed: true, connectionStatus: 'completed' })
          onCompletedRef.current?.(completedEvent)
        }
      } catch (reason) {
        if (!isCurrent()) return
        publish({ error: reason instanceof Error ? reason : new Error('实时日志读取失败') })
        retryTimer = window.setTimeout(() => {
          retryTimer = undefined
          void drain()
        }, INCREMENT_RETRY_DELAY_MS)
      } finally {
        draining = false
        if (isCurrent()) publish({ isFetching: false })
      }
    }
    const connect = () => {
      if (!isCurrent() || completedEvent) return
      if (typeof EventSource === 'undefined') {
        publish({ error: new Error('当前浏览器不支持实时日志连接') })
        return
      }
      publish({
        connectionStatus:
          reconnectDelay > RECONNECT_INITIAL_DELAY_MS ? 'reconnecting' : 'connecting'
      })
      const source = new EventSource(
        `/api/tasks/${encodeURIComponent(taskId!)}/log-notifications?afterEventId=${cursor}`,
        { withCredentials: true }
      )
      eventSource = source
      source.onopen = () => {
        if (!isCurrent() || eventSource !== source) return
        const recovered = reconnectDelay > RECONNECT_INITIAL_DELAY_MS
        reconnectDelay = RECONNECT_INITIAL_DELAY_MS
        publish({ connectionStatus: 'connected' })
        if (recovered) void drain()
      }
      source.addEventListener('task.log.updated', (rawEvent) => {
        if (!isCurrent() || eventSource !== source) return
        const event = parseEvent<ProjectTaskLogUpdatedEvent>(rawEvent)
        if (!event || event.taskId !== taskId) return
        targetCursor = Math.max(targetCursor, event.latestEventId)
        void drain()
      })
      source.addEventListener('task.log.completed', (rawEvent) => {
        if (!isCurrent() || eventSource !== source) return
        const event = parseEvent<ProjectTaskLogCompletedEvent>(rawEvent)
        if (!event || event.taskId !== taskId) return
        completedEvent = event
        targetCursor = Math.max(targetCursor, event.latestEventId)
        closeSource()
        void drain()
      })
      source.onerror = () => {
        if (!isCurrent() || eventSource !== source) return
        closeSource()
        publish({ connectionStatus: 'reconnecting' })
        const delay = reconnectDelay
        reconnectDelay = Math.min(reconnectDelay * 2, RECONNECT_MAX_DELAY_MS)
        reconnectTimer = window.setTimeout(connect, delay)
      }
    }
    const retrySession = () => {
      pendingDrain = true
      void drain()
    }
    retryRef.current = retrySession
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') void drain()
    }
    const dispose = () => {
      disposed = true
      if (retryRef.current === retrySession) retryRef.current = undefined
      closeSource()
      clearRetry()
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
    const unsubscribe = subscribeAuthSession(dispose)
    publish(state)
    if (enabled && taskId) {
      document.addEventListener('visibilitychange', handleVisibilityChange)
      connect()
      void drain()
    }
    return () => {
      unsubscribe()
      dispose()
    }
  }, [enabled, generation, mutateAsync, taskId])
  return {
    ...(enabled && session.generation === generation && session.taskId === taskId
      ? session.state
      : initialState()),
    retry
  }
}
