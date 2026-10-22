import { useQuery } from '@tanstack/react-query'

import {
  createProjectEvaluationReport,
  getProjectEvaluationReport,
  getProjectEvaluationReportDownloadUrl,
  getProjectEvaluationReportLatest
} from '@/api/project/assessment-report'
import { getProjectStageReadiness } from '@/api/project/workflow'
import { useSessionMutation } from '@/hooks/useSessionMutation'
import type { ProjectEvaluationReportDownloadFormat } from '@/types/project'
import { feedback } from '@/utils/feedback'

import { projectQueryKeys } from '../../queryKeys'
import { useStageSubmission } from '../components/useStageSubmission'
export function useAssessmentReportDrawer(
  projectId: string | undefined,
  enabled: boolean,
  recordId?: string
) {
  const reportQueryKey = projectQueryKeys.evaluationReports(projectId)
  const readinessQuery = useQuery({
    queryKey: projectQueryKeys.readiness(projectId, 'report'),
    queryFn: () => getProjectStageReadiness(projectId ?? '', 'report'),
    enabled: enabled && Boolean(projectId)
  })
  const latestQuery = useQuery({
    queryKey: [...reportQueryKey, 'latest'],
    queryFn: () => getProjectEvaluationReportLatest(projectId ?? ''),
    enabled: enabled && Boolean(projectId)
  })
  const selected = useQuery({
    queryKey: projectQueryKeys.evaluationReport(recordId),
    queryFn: () => getProjectEvaluationReport(recordId ?? ''),
    enabled: Boolean(recordId)
  })
  const submission = useStageSubmission(
    latestQuery.data?.execution?.id ?? latestQuery.data?.result?.id,
    `${projectId}:${readinessQuery.data?.context.sourceRevisionId}:${readinessQuery.data?.context.runtimeEnvironmentVersion}`
  )
  const sourceRevisionId = readinessQuery.data?.context.sourceRevisionId ?? undefined
  const generationPrerequisites = ['KB_SCAN', 'DEPENDENCY_ANALYSIS', 'INCLUDED_FINDINGS'].map(
    (key) => readinessQuery.data?.prerequisites.find((item) => item.key === key)
  )
  const canGenerate = generationPrerequisites.every(
    (prerequisite) => prerequisite?.status === 'SATISFIED'
  )
  const latestReport = latestQuery.data?.freshness === 'CURRENT' ? latestQuery.data.result : null
  const report = recordId
    ? selected.data
    : latestReport && latestQuery.data?.execution
      ? { ...latestReport, status: latestQuery.data.execution.status }
      : latestReport
  const { mutateAsync: createReport, isPending: isCreating } = useSessionMutation({
    sessionKey: `report:${projectId}:${sourceRevisionId}`,
    active: enabled,
    mutationFn: () => createProjectEvaluationReport(projectId ?? '', sourceRevisionId ?? undefined),
    onSuccess: () => {
      submission.markSubmitted()
      feedback.success('评估报告生成任务已创建')
    }
  })

  const handleCreate = async () => {
    if (!canGenerate) {
      feedback.error('请先完成评估报告的前置条件')
      return
    }
    await createReport()
  }
  const handleDownload = (format: ProjectEvaluationReportDownloadFormat) => {
    if (!report) return
    window.open(
      getProjectEvaluationReportDownloadUrl(report.id, format),
      '_blank',
      'noopener,noreferrer'
    )
  }

  return {
    canGenerate: canGenerate && !readinessQuery.isError && !latestQuery.isError,
    readinessQuery,
    latestQuery,
    selected,
    submitted: submission.pending,
    generationPrerequisites,
    handleCreate,
    handleDownload,
    isCreating,
    isError: enabled && (readinessQuery.isError || latestQuery.isError),
    isLoading: enabled && (readinessQuery.isLoading || latestQuery.isLoading),
    latestFreshness: latestQuery.data?.freshness,
    refetch: () => Promise.all([readinessQuery.refetch(), latestQuery.refetch()]),
    report,
    sourceRevisionId
  }
}
