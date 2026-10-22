import { useEffect, useRef, useState } from 'react'
import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import type { RefObject } from 'react'

import {
  createModelProfile,
  deleteModelProfile,
  getAgentRuntimes,
  getModelProfileAgentTestRun,
  getModelProfiles,
  getModelStageAssignments,
  testModelProfileAgents,
  testModelProfileConnectivity,
  updateModelProfile,
  updateModelStageAssignments
} from '@/api/admin/models'
import { readAllPages } from '@/api/readAllPages'
import type { BaseTableHandle } from '@/components/BaseTable'
import { useSessionMutation } from '@/hooks/useSessionMutation'
import type {
  ModelProfile,
  ModelProfileAgentProbeRunStatus,
  ModelProfilePayload,
  ModelProfileStage,
  ModelStageAssignment
} from '@/types/admin/models'
import { feedback } from '@/utils/feedback'

import { isActiveProbeStatus, modelStages } from './presentation'
import { modelQueryKeys } from './queryKeys'
import type { BindingMutationVariables, TestProfileVariables } from './types'

export function useModelProfiles(tableRef: RefObject<BaseTableHandle | null>) {
  const [editingStage, setEditingStage] = useState<ModelProfileStage | null>(null)
  const [modalProfile, setModalProfile] = useState<ModelProfile | null | undefined>()
  const [testModalProfile, setTestModalProfile] = useState<ModelProfile | null>(null)
  const processedProbeRunIdsRef = useRef(new Set<string>())
  const queryClient = useQueryClient()
  const assignmentsQuery = useQuery({
    queryKey: modelQueryKeys.assignments(),
    queryFn: getModelStageAssignments
  })
  const agentRuntimesQuery = useQuery({
    queryKey: modelQueryKeys.runtimes(),
    queryFn: getAgentRuntimes
  })
  const modelProfilesStateQuery = useQuery({
    queryKey: modelQueryKeys.profilesState(),
    queryFn: ({ signal }) =>
      readAllPages((page, pageSize) => getModelProfiles({ page, pageSize }), { signal })
  })
  const assignments = new Map<ModelProfileStage, ModelStageAssignment>(
    (assignmentsQuery.data ?? []).map((assignment) => [assignment.stage, assignment])
  )
  const activeProbeRuns = (modelProfilesStateQuery.data?.items ?? []).flatMap((profile) =>
    profile.activeAgentProbeRun ? [profile.activeAgentProbeRun] : []
  )
  const activeProbeRunQueries = useQueries({
    queries: activeProbeRuns.map((run) => ({
      queryKey: modelQueryKeys.probeRun(run.runId),
      queryFn: () => getModelProfileAgentTestRun(run.runId),
      refetchInterval: (query: {
        state: { data?: { status?: ModelProfileAgentProbeRunStatus } }
      }) => (isActiveProbeStatus(query.state.data?.status ?? run.status) ? 2_000 : false)
    }))
  })
  useEffect(() => {
    const completedRunIds = activeProbeRunQueries.flatMap((query) => {
      const run = query.data
      return run && !isActiveProbeStatus(run.status) ? [run.id] : []
    })
    const unprocessedRunIds = completedRunIds.filter(
      (runId) => !processedProbeRunIdsRef.current.has(runId)
    )
    if (unprocessedRunIds.length === 0) return
    unprocessedRunIds.forEach((runId) => processedProbeRunIdsRef.current.add(runId))
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: modelQueryKeys.profilesState() }),
      queryClient.invalidateQueries({ queryKey: modelQueryKeys.profiles() }),
      queryClient.invalidateQueries({ queryKey: modelQueryKeys.assignments() })
    ])
  }, [activeProbeRunQueries, queryClient])

  const saveProfileMutation = useSessionMutation({
    sessionKey: modalProfile?.id ?? 'new-profile',
    active: modalProfile !== undefined,
    mutationFn: (values: ModelProfilePayload) => {
      if (modalProfile) return updateModelProfile(modalProfile.id, values)
      return createModelProfile({
        apiKey: values.apiKey ?? '',
        baseUrl: values.baseUrl ?? '',
        enabled: values.enabled ?? true,
        executablePath: values.executablePath ?? 'codex',
        maxRuntimeSeconds: values.maxRuntimeSeconds,
        model: values.model ?? '',
        modelProviderType: 'OPENAI_COMPATIBLE',
        name: values.name ?? '',
        timeoutSeconds: values.timeoutSeconds,
        wireApi: values.wireApi ?? 'RESPONSES'
      })
    },
    onSuccess: async () => {
      setModalProfile(undefined)
      feedback.success('模型 Profile 已保存')
      await Promise.all([
        tableRef.current?.reload(),
        queryClient.invalidateQueries({ queryKey: modelQueryKeys.assignments() }),
        queryClient.invalidateQueries({ queryKey: modelQueryKeys.profilesState() })
      ])
    }
  })
  const bindingMutation = useSessionMutation({
    sessionKey: `model-binding:${editingStage}`,
    active: editingStage !== null,
    mutationFn: ({ agentRuntimeId, modelProfileId, stage }: BindingMutationVariables) =>
      updateModelStageAssignments(stage, modelProfileId, agentRuntimeId),
    onSuccess: async (_, variables) => {
      const title = modelStages.find((item) => item.stage === variables.stage)?.title ?? '阶段'
      setEditingStage(null)
      feedback.success(`${title}模型与 Agent 已绑定`)
      await queryClient.invalidateQueries({ queryKey: modelQueryKeys.assignments() })
    }
  })
  const connectivityMutation = useSessionMutation({
    sessionKey: 'model-connectivity',
    active: true,
    mutationFn: testModelProfileConnectivity,
    onSuccess: async (result) => {
      if (result.success) feedback.success('模型 Provider 连通性测试通过')
      else feedback.error(result.message)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: modelQueryKeys.profilesState() }),
        queryClient.invalidateQueries({ queryKey: modelQueryKeys.profiles() })
      ])
    }
  })
  const agentProbeMutation = useSessionMutation({
    sessionKey: testModalProfile?.id ?? 'test-profile',
    active: Boolean(testModalProfile),
    mutationFn: ({ agentRuntimeIds, profileId }: TestProfileVariables) =>
      testModelProfileAgents(profileId, agentRuntimeIds),
    onSuccess: async () => {
      setTestModalProfile(null)
      feedback.success('Agent 兼容性测试已开始')
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: modelQueryKeys.profilesState() }),
        queryClient.invalidateQueries({ queryKey: modelQueryKeys.profiles() }),
        queryClient.invalidateQueries({ queryKey: modelQueryKeys.assignments() })
      ])
    }
  })
  const updateStatusMutation = useSessionMutation({
    sessionKey: 'model-status',
    active: true,
    mutationFn: ({ enabled, profileId }: { enabled: boolean; profileId: string }) =>
      updateModelProfile(profileId, { enabled }),
    onSuccess: async () => {
      feedback.success('模型 Profile 状态已更新')
      await Promise.all([
        tableRef.current?.reload(),
        queryClient.invalidateQueries({ queryKey: modelQueryKeys.assignments() }),
        queryClient.invalidateQueries({ queryKey: modelQueryKeys.profilesState() })
      ])
    }
  })
  const deleteMutation = useSessionMutation({
    sessionKey: 'model-delete',
    active: true,
    mutationFn: deleteModelProfile,
    onSuccess: async () => {
      feedback.success('模型 Profile 已删除')
      await Promise.all([
        tableRef.current?.reload(),
        queryClient.invalidateQueries({ queryKey: modelQueryKeys.profilesState() })
      ])
    }
  })

  return {
    editingStage,
    setEditingStage,
    modalProfile,
    setModalProfile,
    testModalProfile,
    setTestModalProfile,
    assignmentsQuery,
    agentRuntimesQuery,
    modelProfilesStateQuery,
    assignments,
    saveProfileMutation,
    bindingMutation,
    connectivityMutation,
    agentProbeMutation,
    updateStatusMutation,
    deleteMutation
  }
}
