import { useState } from 'react'
import { useIsFetching, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createProjectDependencyAnalysis,
  getProjectDependencyAnalysisLatest,
  getProjectDependencyAnalysisResult
} from '@/api/project/dependency-analysis'
import { getProjectStageReadiness } from '@/api/project/workflow'
import { useSessionMutation } from '@/hooks/useSessionMutation'
import type { ProjectDependencyAnalysis } from '@/types/project/dependency-analysis'
import { feedback } from '@/utils/feedback'

import { projectQueryKeys } from '../../queryKeys'
import { useStageSubmission } from '../components/useStageSubmission'

type View =
  | { type: 'latest' }
  | { type: 'history' }
  | { type: 'history-analysis'; analysis: ProjectDependencyAnalysis }
  | { type: 'latest-result'; analysis: ProjectDependencyAnalysis; resultId: string }
  | { type: 'history-result'; analysis: ProjectDependencyAnalysis; resultId: string }

export function useDependencyAnalysisDrawer(projectId: string | undefined, visible: boolean) {
  const queryClient = useQueryClient()
  const [view, setView] = useState<View>({ type: 'latest' })
  const isLatestView = view.type === 'latest'
  const selectedResultId =
    view.type === 'latest-result' || view.type === 'history-result' ? view.resultId : undefined
  const selectedResultQuery = useQuery({
    queryKey: projectQueryKeys.dependencyAnalysisResult(selectedResultId),
    queryFn: () => getProjectDependencyAnalysisResult(selectedResultId ?? ''),
    enabled: visible && Boolean(selectedResultId)
  })
  const readinessQuery = useQuery({
    queryKey: projectQueryKeys.readiness(projectId, 'rv-dependency-analysis'),
    queryFn: () => getProjectStageReadiness(projectId ?? '', 'rv-dependency-analysis'),
    enabled: visible && Boolean(projectId) && isLatestView
  })
  const readinessSourceRevisionId = readinessQuery.data?.context.sourceRevisionId ?? undefined
  const analysisRecordsKey = projectQueryKeys.dependencyAnalyses(projectId)
  const analysisKey = analysisRecordsKey
  const historyIsFetching = useIsFetching({ queryKey: analysisRecordsKey }) > 0
  const latestAnalysisQuery = useQuery({
    queryKey: projectQueryKeys.dependencyAnalysisLatest(projectId),
    queryFn: () => getProjectDependencyAnalysisLatest(projectId ?? ''),
    enabled: visible && Boolean(projectId) && isLatestView
  })
  const submission = useStageSubmission(
    latestAnalysisQuery.data?.execution?.id ?? latestAnalysisQuery.data?.result?.id,
    `${projectId}:${readinessSourceRevisionId}:${readinessQuery.data?.context.runtimeEnvironmentVersion}`
  )
  const createMutation = useSessionMutation({
    sessionKey: `dependency-analysis:${projectId}:${readinessSourceRevisionId}`,
    active: visible && isLatestView,
    mutationFn: () =>
      createProjectDependencyAnalysis(projectId ?? '', {
        sourceRevisionId: readinessSourceRevisionId
      }),
    onSuccess: () => {
      setView({ type: 'latest' })
      submission.markSubmitted()
      feedback.success('依赖分析任务已创建')
    }
  })
  const latestAnalysis =
    latestAnalysisQuery.data?.freshness === 'CURRENT' ? latestAnalysisQuery.data.result : null
  const isError = isLatestView && (readinessQuery.isError || latestAnalysisQuery.isError)
  const isLoading = isLatestView && (readinessQuery.isLoading || latestAnalysisQuery.isLoading)
  const refetch = () => Promise.all([readinessQuery.refetch(), latestAnalysisQuery.refetch()])
  return {
    queryClient,
    submitted: submission.pending,
    view,
    setView,
    selectedResultQuery,
    readinessQuery,
    readinessSourceRevisionId,
    analysisKey,
    historyIsFetching,
    createMutation,
    latestAnalysisQuery,
    latestAnalysis,
    isError,
    isLoading,
    refetch
  }
}
