import { useEffect, useSyncExternalStore } from 'react'
import { type QueryKey, useQueryClient } from '@tanstack/react-query'

import { getProjectTaskTypeText } from '@/config/project-status'
import {
  getAuthGeneration,
  isAuthGenerationCurrent,
  subscribeAuthSession
} from '@/store/authSession'
import type { ProjectTaskStatus } from '@/types/project/task'
import { appNotification } from '@/utils/appNotification'

import { projectCurrentContextDependentQueryKeys, projectQueryKeys } from './queryKeys'

const TERMINAL_TASK_EVENTS = [
  'task.succeeded',
  'task.failed',
  'task.cancelled',
  'task.timeout'
] as const
const OVERVIEW_TASK_EVENTS = [
  'task.created',
  'task.queued',
  'task.started',
  'task.progress',
  ...TERMINAL_TASK_EVENTS
] as const
const SUBSCRIBED_PROJECT_EVENTS = [
  ...OVERVIEW_TASK_EVENTS,
  'task.log',
  'project.context.changed'
] as const
const SSE_RECONNECT_INITIAL_DELAY_MS = 1_000
const SSE_RECONNECT_MAX_DELAY_MS = 30_000
const OVERVIEW_CONTEXT_REFRESH_BATCH_MS = 250
const OVERVIEW_TASK_LIFECYCLE_REFRESH_BATCH_MS = 5_000
const DOMAIN_REFRESH_BATCH_MS = 250
const OVERVIEW_PROGRESS_REFRESH_THROTTLE_MS = 10_000

interface ProjectTaskEvent {
  changedFields?: string[]
  id?: number
  message?: string | null
  progress?: number | null
  projectId?: string
  resource?: {
    environmentRole?: string | null
    id?: string | null
    mode?: string | null
    type?: string | null
  }
  stageId?: string | null
  status?: ProjectTaskStatus | null
  taskId?: string | null
  taskType?: string | null
}

function eventIdOf(event: MessageEvent<string>, taskEvent: ProjectTaskEvent) {
  const value = event.lastEventId || taskEvent.id
  const eventId = typeof value === 'number' ? value : Number(value)
  return Number.isSafeInteger(eventId) && eventId >= 0 ? eventId : null
}

function isTerminalTaskEvent(eventType: string) {
  return TERMINAL_TASK_EVENTS.includes(eventType as (typeof TERMINAL_TASK_EVENTS)[number])
}

function notifyTerminalTask(
  eventType: string,
  taskEvent: ProjectTaskEvent,
  eventId: number | null
) {
  const taskName = taskEvent.taskType ? getProjectTaskTypeText(taskEvent.taskType) : '任务'
  const key = eventId === null ? undefined : `project-task-event-${eventId}`

  switch (eventType) {
    case 'task.succeeded':
      appNotification.success({
        description: taskEvent.message || '执行结果已更新',
        key,
        title: `${taskName}已完成`
      })
      break
    case 'task.failed':
      appNotification.error({
        description: taskEvent.message || '请查看任务详情和执行日志',
        duration: 8,
        key,
        title: `${taskName}执行失败`
      })
      break
    case 'task.timeout':
      appNotification.error({
        description: taskEvent.message || '任务执行超时，请检查环境或重新执行',
        duration: 8,
        key,
        title: `${taskName}执行超时`
      })
      break
    case 'task.cancelled':
      appNotification.warning({
        description: taskEvent.message || '任务已停止执行',
        key,
        title: `${taskName}已取消`
      })
      break
  }
}

function stageQueryKeys(
  projectId: string,
  taskEvent: ProjectTaskEvent,
  eventType: (typeof OVERVIEW_TASK_EVENTS)[number]
): QueryKey[] {
  const terminal = isTerminalTaskEvent(eventType)
  const succeeded = eventType === 'task.succeeded'
  const archiveReadinessKeys = succeeded ? [projectQueryKeys.readiness(projectId, 'archive')] : []

  switch (taskEvent.stageId) {
    case 'source':
      return taskEvent.resource?.type === 'source_deploy_run'
        ? [projectQueryKeys.optimizationCycles(projectId)]
        : []
    case 'environment':
      if (terminal && taskEvent.resource?.mode === 'CUSTOM_BASH' && taskEvent.resource.id) {
        return [['project-environment-script-executions', projectId, taskEvent.resource.id]]
      }
      return terminal
        ? [projectQueryKeys.environments(projectId), projectQueryKeys.environmentOptions(projectId)]
        : []
    case 'memory-order-analysis':
    case 'floating-point-analysis':
      return [
        projectQueryKeys.specializedAnalyses(projectId, taskEvent.stageId),
        projectQueryKeys.readiness(projectId, taskEvent.stageId),
        ...archiveReadinessKeys
      ]
    case 'x86-build':
      return [
        ['project-build-validations', projectId, 'SOURCE_ONLY'],
        projectQueryKeys.automatedTestBuildInputs(projectId),
        projectQueryKeys.readiness(projectId, 'kb'),
        projectQueryKeys.readiness(projectId, 'memory-order-analysis'),
        projectQueryKeys.readiness(projectId, 'floating-point-analysis'),
        projectQueryKeys.specializedAnalyses(projectId),
        projectQueryKeys.readiness(projectId, 'rv-dependency-analysis'),
        projectQueryKeys.optimizationCycles(projectId),
        ...archiveReadinessKeys
      ]
    case 'kb-scan':
      if (taskEvent.resource?.type === 'kb_ai_extension_run') {
        return [
          projectQueryKeys.knowledgeBaseAiExtensions(projectId),
          ...(terminal
            ? ([
                ['project-knowledge-base-findings'],
                ['project-knowledge-base-finding']
              ] as QueryKey[])
            : []),
          ...archiveReadinessKeys
        ]
      }
      return [
        projectQueryKeys.knowledgeBaseScans(projectId),
        projectQueryKeys.readiness(projectId, 'report'),
        ...archiveReadinessKeys
      ]
    case 'dependency-analysis':
      return taskEvent.resource?.type === 'dependency_auto_fix_run'
        ? []
        : [
            projectQueryKeys.dependencyAnalyses(projectId),
            projectQueryKeys.readiness(projectId, 'report'),
            ...archiveReadinessKeys
          ]
    case 'evaluation-report':
      return [
        ...(taskEvent.resource?.type === 'report'
          ? [projectQueryKeys.evaluationReports(projectId)]
          : []),
        ...(['report', 'recheck_run'].includes(taskEvent.resource?.type ?? '')
          ? [projectQueryKeys.optimizationCycles(projectId)]
          : []),
        ...(['report', 'report_comparison_run', 'recheck_run'].includes(
          taskEvent.resource?.type ?? ''
        )
          ? archiveReadinessKeys
          : [])
      ]
    case 'build-validation':
      return [
        ['project-build-validations', projectId, 'VALIDATION'],
        projectQueryKeys.automatedTestBuildInputs(projectId),
        projectQueryKeys.readiness(projectId, 'test'),
        projectQueryKeys.optimizationCycles(projectId),
        ...archiveReadinessKeys
      ]
    case 'automated-test':
      return taskEvent.resource?.type === 'test_comparison_run'
        ? [
            projectQueryKeys.testComparisons(projectId),
            projectQueryKeys.optimizationCycles(projectId),
            ...archiveReadinessKeys
          ]
        : [
            projectQueryKeys.automatedTests(projectId),
            projectQueryKeys.testComparisons(projectId),
            projectQueryKeys.optimizationCycles(projectId),
            ...archiveReadinessKeys
          ]
    case 'archive':
      return [projectQueryKeys.archives(projectId)]
    default:
      return []
  }
}

function contextQueryKeys(projectId: string, taskEvent: ProjectTaskEvent): QueryKey[] {
  const changedFields = new Set(taskEvent.changedFields ?? [])
  const sourceChanged =
    taskEvent.resource?.type === 'source_revision' || changedFields.has('activeSourceRevision')
  const environmentChanged =
    taskEvent.resource?.type === 'environment' ||
    taskEvent.resource?.type === 'project_runtime_environment' ||
    [...changedFields].some(
      (field) => field.startsWith('runtimeEnvironment.') || field === 'environment.config'
    )
  const queryKeys: QueryKey[] = []

  if (sourceChanged) {
    queryKeys.push(...projectCurrentContextDependentQueryKeys(projectId, 'source'))
  }
  if (environmentChanged) {
    queryKeys.push(
      projectQueryKeys.environments(projectId),
      projectQueryKeys.environmentOptions(projectId),
      ...projectCurrentContextDependentQueryKeys(projectId, 'runtime-environments')
    )
  }
  if (!sourceChanged && !environmentChanged) {
    queryKeys.push(
      projectQueryKeys.environments(projectId),
      projectQueryKeys.environmentOptions(projectId),
      ...projectCurrentContextDependentQueryKeys(projectId, 'source')
    )
  }

  const uniqueKeys = new Map(queryKeys.map((queryKey) => [JSON.stringify(queryKey), queryKey]))
  return [...uniqueKeys.values()]
}

export function useProjectTaskEvents(projectId?: string, initialEventCursor?: number) {
  const queryClient = useQueryClient()
  const generation = useSyncExternalStore(
    subscribeAuthSession,
    getAuthGeneration,
    getAuthGeneration
  )

  useEffect(() => {
    if (!projectId || initialEventCursor === undefined) return

    let lastAppliedEventId = initialEventCursor
    let eventSource: EventSource | undefined
    let reconnectTimer: number | undefined
    let overviewContextRefreshTimer: number | undefined
    let overviewTaskLifecycleRefreshTimer: number | undefined
    const domainRefreshTimers = new Map<string, number>()
    let overviewProgressRefreshTimer: number | undefined
    let reconnectDelay = SSE_RECONNECT_INITIAL_DELAY_MS
    let disposed = false
    const isCurrent = () => !disposed && isAuthGenerationCurrent(generation)

    const clearOverviewTaskLifecycleRefresh = () => {
      if (overviewTaskLifecycleRefreshTimer === undefined) return
      window.clearTimeout(overviewTaskLifecycleRefreshTimer)
      overviewTaskLifecycleRefreshTimer = undefined
    }

    const clearOverviewProgressRefresh = () => {
      if (overviewProgressRefreshTimer !== undefined) {
        window.clearTimeout(overviewProgressRefreshTimer)
        overviewProgressRefreshTimer = undefined
      }
    }

    const scheduleOverviewContextRefresh = () => {
      clearOverviewTaskLifecycleRefresh()
      clearOverviewProgressRefresh()
      if (overviewContextRefreshTimer !== undefined) return
      overviewContextRefreshTimer = window.setTimeout(() => {
        overviewContextRefreshTimer = undefined
        if (isCurrent()) {
          void queryClient.invalidateQueries({ queryKey: projectQueryKeys.overview(projectId) })
        }
      }, OVERVIEW_CONTEXT_REFRESH_BATCH_MS)
    }

    const scheduleOverviewTaskLifecycleRefresh = () => {
      clearOverviewProgressRefresh()
      if (
        overviewContextRefreshTimer !== undefined ||
        overviewTaskLifecycleRefreshTimer !== undefined
      ) {
        return
      }
      overviewTaskLifecycleRefreshTimer = window.setTimeout(() => {
        overviewTaskLifecycleRefreshTimer = undefined
        if (isCurrent()) {
          void queryClient.invalidateQueries({ queryKey: projectQueryKeys.overview(projectId) })
        }
      }, OVERVIEW_TASK_LIFECYCLE_REFRESH_BATCH_MS)
    }

    const refreshDomainQueries = (queryKeys: QueryKey[], immediate: boolean) => {
      if (!isCurrent()) return
      for (const queryKey of queryKeys) {
        const timerKey = JSON.stringify(queryKey)
        const existingTimer = domainRefreshTimers.get(timerKey)

        if (immediate) {
          if (existingTimer !== undefined) window.clearTimeout(existingTimer)
          domainRefreshTimers.delete(timerKey)
          void queryClient.invalidateQueries({ queryKey })
          continue
        }

        if (existingTimer !== undefined) continue
        const timer = window.setTimeout(() => {
          domainRefreshTimers.delete(timerKey)
          if (isCurrent()) {
            void queryClient.invalidateQueries({ queryKey }, { cancelRefetch: false })
          }
        }, DOMAIN_REFRESH_BATCH_MS)
        domainRefreshTimers.set(timerKey, timer)
      }
    }

    const scheduleOverviewProgressRefresh = () => {
      if (
        overviewContextRefreshTimer !== undefined ||
        overviewTaskLifecycleRefreshTimer !== undefined ||
        overviewProgressRefreshTimer !== undefined
      ) {
        return
      }
      overviewProgressRefreshTimer = window.setTimeout(() => {
        overviewProgressRefreshTimer = undefined
        if (isCurrent()) {
          void queryClient.invalidateQueries({ queryKey: projectQueryKeys.overview(projectId) })
        }
      }, OVERVIEW_PROGRESS_REFRESH_THROTTLE_MS)
    }

    const createTaskEventHandler =
      (eventType: (typeof SUBSCRIBED_PROJECT_EVENTS)[number]) => (event: MessageEvent<string>) => {
        if (!isCurrent()) return
        let taskEvent: ProjectTaskEvent
        try {
          taskEvent = JSON.parse(event.data) as ProjectTaskEvent
        } catch {
          return
        }
        if (taskEvent.projectId && taskEvent.projectId !== projectId) return

        const eventId = eventIdOf(event, taskEvent)
        if (eventId !== null) {
          if (eventId <= lastAppliedEventId) return
          lastAppliedEventId = eventId
        }

        if (eventType === 'task.log') return

        if (eventType === 'project.context.changed') {
          scheduleOverviewContextRefresh()
          void Promise.all(
            contextQueryKeys(projectId, taskEvent).map((queryKey) =>
              queryClient.invalidateQueries({ queryKey })
            )
          )
          return
        }

        if (!taskEvent.stageId) return

        const terminal = isTerminalTaskEvent(eventType)
        if (terminal) notifyTerminalTask(eventType, taskEvent, eventId)

        if (terminal) {
          void refreshOverview()
        } else if (eventType === 'task.progress') {
          scheduleOverviewProgressRefresh()
        } else {
          scheduleOverviewTaskLifecycleRefresh()
        }
        const queryKeys: QueryKey[] = []
        if (eventType !== 'task.progress') {
          queryKeys.push(...stageQueryKeys(projectId, taskEvent, eventType))
        }

        refreshDomainQueries(queryKeys, terminal)
      }

    const taskEventListeners = SUBSCRIBED_PROJECT_EVENTS.map(
      (eventType) => [eventType, createTaskEventHandler(eventType)] as const
    )

    const refreshOverview = () => {
      if (!isCurrent()) return
      if (overviewContextRefreshTimer !== undefined) {
        window.clearTimeout(overviewContextRefreshTimer)
        overviewContextRefreshTimer = undefined
      }
      clearOverviewTaskLifecycleRefresh()
      clearOverviewProgressRefresh()
      return queryClient.invalidateQueries({ queryKey: projectQueryKeys.overview(projectId) })
    }
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') void refreshOverview()
    }

    const detachEventSource = (source: EventSource) => {
      for (const [eventType, handler] of taskEventListeners) {
        source.removeEventListener(eventType, handler)
      }
      source.onopen = null
      source.onerror = null
    }
    const connect = () => {
      if (!isCurrent()) return

      const source = new EventSource(
        `/api/projects/${projectId}/task-events?afterEventId=${lastAppliedEventId}`,
        { withCredentials: true }
      )
      eventSource = source

      source.onopen = () => {
        if (!isCurrent() || eventSource !== source) return
        reconnectDelay = SSE_RECONNECT_INITIAL_DELAY_MS
      }
      source.onerror = () => {
        if (!isCurrent() || eventSource !== source) return
        detachEventSource(source)
        source.close()
        eventSource = undefined

        if (disposed || reconnectTimer !== undefined) return
        const delay = reconnectDelay
        reconnectDelay = Math.min(reconnectDelay * 2, SSE_RECONNECT_MAX_DELAY_MS)
        reconnectTimer = window.setTimeout(() => {
          reconnectTimer = undefined
          connect()
        }, delay)
      }

      for (const [eventType, handler] of taskEventListeners) {
        source.addEventListener(eventType, handler)
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    connect()

    const dispose = () => {
      disposed = true
      if (reconnectTimer !== undefined) {
        window.clearTimeout(reconnectTimer)
        reconnectTimer = undefined
      }
      if (overviewContextRefreshTimer !== undefined) {
        window.clearTimeout(overviewContextRefreshTimer)
        overviewContextRefreshTimer = undefined
      }
      clearOverviewTaskLifecycleRefresh()
      clearOverviewProgressRefresh()
      for (const timer of domainRefreshTimers.values()) window.clearTimeout(timer)
      domainRefreshTimers.clear()
      if (eventSource) {
        detachEventSource(eventSource)
        eventSource.close()
        eventSource = undefined
      }
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
    const unsubscribe = subscribeAuthSession(dispose)
    return () => {
      unsubscribe()
      dispose()
    }
  }, [generation, initialEventCursor, projectId, queryClient])
}
