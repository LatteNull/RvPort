import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'

import {
  cancelProjectAutomatedTest,
  getProjectAutomatedTestLatest,
  getProjectAutomatedTests,
  getProjectTestComparisons
} from '@/api/project/automated-test'
import { getProjectBuildValidations } from '@/api/project/build-validation'
import { getProjectStageReadiness } from '@/api/project/workflow'
import { readAllPages } from '@/api/readAllPages'
import { useSessionMutation } from '@/hooks/useSessionMutation'
import { feedback } from '@/utils/feedback'

import { projectQueryKeys } from '../../queryKeys'
import type { TestBuildContext } from './types'
import { useTestBatchSubmission } from './useTestBatchSubmission'

const terminalStatuses = new Set(['SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT'])

export function isTerminalTestStatus(status?: string) {
  return Boolean(status && terminalStatuses.has(status))
}

interface AutomatedTestDrawerQueryScope {
  submissionEnabled: boolean
  currentEnabled: boolean
  recordsEnabled: boolean
}

export function useAutomatedTestDrawer(
  projectId: string | undefined,
  { currentEnabled, recordsEnabled, submissionEnabled }: AutomatedTestDrawerQueryScope
) {
  const readinessQuery = useQuery({
    queryKey: projectQueryKeys.readiness(projectId, 'test'),
    queryFn: () => getProjectStageReadiness(projectId ?? '', 'test'),
    enabled: currentEnabled && Boolean(projectId)
  })
  const sourceRevisionId = readinessQuery.data?.context.sourceRevisionId ?? undefined
  const buildValidationPrerequisite = readinessQuery.data?.prerequisites.find(
    (item) => item.key === 'BUILD_VALIDATION'
  )
  const ready = buildValidationPrerequisite?.status === 'SATISFIED'
  const latestQuery = useQuery({
    queryKey: [...projectQueryKeys.automatedTests(projectId), 'latest'],
    queryFn: () => getProjectAutomatedTestLatest(projectId ?? ''),
    enabled: currentEnabled && Boolean(projectId)
  })
  const buildsQuery = useQuery({
    queryKey: [...projectQueryKeys.automatedTestBuildInputs(projectId), sourceRevisionId],
    queryFn: ({ signal }) =>
      readAllPages(
        (page, pageSize) =>
          getProjectBuildValidations(projectId ?? '', {
            buildScope: 'BOTH',
            page,
            pageSize,
            sourceRevisionId
          }),
        { pageSize: 100, signal }
      ),
    enabled: currentEnabled && ready && Boolean(projectId) && Boolean(sourceRevisionId)
  })
  const testsQuery = useQuery({
    queryKey: [...projectQueryKeys.automatedTests(projectId), 'records'],
    queryFn: ({ signal }) =>
      readAllPages(
        (page, pageSize) =>
          getProjectAutomatedTests(projectId ?? '', {
            page,
            pageSize,
            sortBy: 'createdAt',
            sortDirection: 'desc'
          }),
        { pageSize: 100, signal }
      ),
    enabled: recordsEnabled && Boolean(projectId)
  })
  const comparisonsQuery = useQuery({
    queryKey: projectQueryKeys.testComparisons(projectId),
    queryFn: ({ signal }) =>
      readAllPages(
        (page, pageSize) => getProjectTestComparisons(projectId ?? '', { page, pageSize }),
        { pageSize: 100, signal }
      ),
    enabled: recordsEnabled && Boolean(projectId)
  })
  const buildContexts = useMemo(() => {
    const builds = buildsQuery.data?.items ?? []
    const details = buildValidationPrerequisite?.details
    const resolveBuild = (role: 'SOURCE' | 'TARGET') => {
      const detailKey = role === 'SOURCE' ? 'sourceBuildRunId' : 'targetBuildRunId'
      const referencedId = typeof details?.[detailKey] === 'string' ? details[detailKey] : undefined
      const build = builds.find((item) => {
        if (referencedId) return item.id === referencedId
        const architecture = item.environment?.arch.toLowerCase() ?? ''
        const matchesRole =
          role === 'SOURCE'
            ? architecture.includes('x86') || architecture.includes('amd64')
            : architecture.includes('riscv')
        return item.status === 'SUCCEEDED' && item.currentRuntimeEnvironment && matchesRole
      })
      return {
        role,
        environment: null,
        build: build ?? null,
        reason: build ? null : '无法读取当前构建输入'
      } satisfies TestBuildContext
    }
    return [resolveBuild('SOURCE'), resolveBuild('TARGET')]
  }, [buildValidationPrerequisite?.details, buildsQuery.data?.items])
  const latestTest = useMemo(() => {
    const latest = latestQuery.data
    const result = latest?.freshness === 'CURRENT' ? latest.result : null
    return result && latest?.execution ? { ...result, status: latest.execution.status } : result
  }, [latestQuery.data])
  const tests = useMemo(() => {
    const records = testsQuery.data?.items ?? []
    if (!latestTest || records.some((item) => item.id === latestTest.id)) return records
    return [latestTest, ...records]
  }, [latestTest, testsQuery.data?.items])
  const batchSubmission = useTestBatchSubmission(projectId, submissionEnabled, buildContexts)
  const cancelMutation = useSessionMutation({
    sessionKey: `cancel-test:${projectId}`,
    active: submissionEnabled,
    mutationFn: cancelProjectAutomatedTest,
    onSuccess: () => {
      feedback.success('测试取消请求已提交')
    }
  })

  return {
    buildValidationPrerequisite,
    buildContexts,
    canCreate:
      ready &&
      !readinessQuery.isError &&
      !buildsQuery.isError &&
      !latestQuery.isError &&
      buildContexts.every((item) => item.build),
    cancelMutation,
    comparisons: comparisonsQuery.data?.items ?? [],
    batchSubmission,
    currentHasData: Boolean(
      readinessQuery.data && latestQuery.data && (!ready || buildsQuery.data)
    ),
    recordsHasData: Boolean(testsQuery.data && comparisonsQuery.data),
    currentError:
      currentEnabled && (readinessQuery.isError || latestQuery.isError || buildsQuery.isError),
    currentLoading:
      currentEnabled &&
      (readinessQuery.isLoading || latestQuery.isLoading || buildsQuery.isLoading),
    recordsError: recordsEnabled && (testsQuery.isError || comparisonsQuery.isError),
    recordsLoading: recordsEnabled && (testsQuery.isLoading || comparisonsQuery.isLoading),
    isError:
      (currentEnabled && (readinessQuery.isError || latestQuery.isError || buildsQuery.isError)) ||
      (recordsEnabled && (testsQuery.isError || comparisonsQuery.isError)),
    isLoading:
      (currentEnabled &&
        (readinessQuery.isLoading || latestQuery.isLoading || buildsQuery.isLoading)) ||
      (recordsEnabled && (testsQuery.isLoading || comparisonsQuery.isLoading)),
    latestFreshness: latestQuery.data?.freshness,
    latestTest,
    ready,
    sourceRevisionId,
    tests,
    refetch: () =>
      Promise.all([
        ...(currentEnabled
          ? [
              readinessQuery.refetch(),
              latestQuery.refetch(),
              ...(ready && sourceRevisionId ? [buildsQuery.refetch()] : [])
            ]
          : []),
        ...(recordsEnabled ? [testsQuery.refetch(), comparisonsQuery.refetch()] : [])
      ])
  }
}
