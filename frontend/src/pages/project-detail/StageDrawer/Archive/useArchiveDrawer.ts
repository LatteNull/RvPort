import { useMemo, useState } from 'react'
import { useIsFetching, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createProjectArchive,
  getProjectArchive,
  getProjectArchiveLatest
} from '@/api/project/archive'
import { getProjectStageReadiness } from '@/api/project/workflow'
import { useSessionMutation } from '@/hooks/useSessionMutation'
import { feedback } from '@/utils/feedback'

import { projectQueryKeys } from '../../queryKeys'
import { useStageSubmission } from '../components/useStageSubmission'

type ArchiveView =
  | { type: 'overview' }
  | { type: 'history' }
  | { type: 'detail'; archiveId: string; returnTo: 'overview' | 'history' }

export function useArchiveDrawer(projectId: string | undefined, visible: boolean) {
  const queryClient = useQueryClient()
  const [view, setView] = useState<ArchiveView>({ type: 'overview' })
  const [isClosing, setIsClosing] = useState(false)
  const currentEnabled = visible && view.type === 'overview' && !isClosing
  const archiveId = view.type === 'detail' ? view.archiveId : undefined
  const detailEnabled = visible && view.type === 'detail' && !isClosing && Boolean(archiveId)
  const isHistoryFetching = useIsFetching({ queryKey: projectQueryKeys.archives(projectId) }) > 0
  const readinessQuery = useQuery({
    queryKey: projectQueryKeys.readiness(projectId, 'archive'),
    queryFn: () => getProjectStageReadiness(projectId ?? '', 'archive'),
    enabled: currentEnabled && Boolean(projectId)
  })
  const latestQuery = useQuery({
    queryKey: projectQueryKeys.archiveLatest(projectId),
    queryFn: () => getProjectArchiveLatest(projectId ?? ''),
    enabled: currentEnabled && Boolean(projectId)
  })
  const detailQuery = useQuery({
    queryKey: projectQueryKeys.archive(archiveId),
    queryFn: () => getProjectArchive(archiveId ?? ''),
    enabled: detailEnabled
  })
  const prerequisites = readinessQuery.data?.prerequisites ?? []
  const latestArchive = useMemo(() => {
    const latest = latestQuery.data
    const result = latest?.result
    return result && latest?.execution
      ? { ...result, status: latest.execution.status }
      : (result ?? null)
  }, [latestQuery.data])
  const submission = useStageSubmission(
    latestQuery.data?.execution?.id ?? latestArchive?.id,
    `${projectId}:${readinessQuery.data?.context.sourceRevisionId}:${readinessQuery.data?.context.runtimeEnvironmentVersion}`
  )
  const createMutation = useSessionMutation({
    sessionKey: `archive:${projectId}`,
    active: currentEnabled,
    mutationFn: () => createProjectArchive(projectId ?? ''),
    onSuccess: () => {
      submission.markSubmitted()
      feedback.success('归档任务已创建')
    }
  })

  return {
    archive: detailQuery.data,
    latestQuery,
    readinessQuery,
    submitted: submission.pending,
    canCreate:
      prerequisites.length > 0 && prerequisites.every((item) => item.status === 'SATISFIED'),
    close: () => setIsClosing(true),
    create: createMutation.mutateAsync,
    finishClose: () => {
      setIsClosing(false)
      setView({ type: 'overview' })
    },
    freshness: latestQuery.data?.freshness,
    isCreating: createMutation.isPending,
    isDetailError: detailEnabled && detailQuery.isError,
    isDetailLoading: detailEnabled && detailQuery.isLoading,
    isError: currentEnabled && (readinessQuery.isError || latestQuery.isError),
    isHistoryFetching,
    isLoading: currentEnabled && (readinessQuery.isLoading || latestQuery.isLoading),
    latestArchive,
    prerequisites,
    refreshCurrent: () => Promise.all([readinessQuery.refetch(), latestQuery.refetch()]),
    refreshHistory: () =>
      queryClient.invalidateQueries({ queryKey: projectQueryKeys.archives(projectId) }),
    refetchDetail: detailQuery.refetch,
    showDetail: (nextArchiveId: string, returnTo: 'overview' | 'history' = 'history') =>
      setView({ type: 'detail', archiveId: nextArchiveId, returnTo }),
    showHistory: () => setView({ type: 'history' }),
    showOverview: () => setView({ type: 'overview' }),
    view
  }
}
