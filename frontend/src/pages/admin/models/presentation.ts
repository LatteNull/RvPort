import type {
  ModelProfile,
  ModelProfileAgentProbeResult,
  ModelProfileAgentProbeRunStatus,
  ModelStageAssignment
} from '@/types/admin/models'

import type { ModelStagePresentation } from './types'

import styles from './index.module.scss'
export const modelStages: ModelStagePresentation[] = [
  {
    readyText: '测试结果比较可用',
    stage: 'TEST_LOG_COMPARE',
    title: '测试结果比较'
  },
  {
    readyText: '知识库 AI 扩展可用',
    stage: 'KB_AI_EXTENSION',
    title: '知识库 AI 扩展'
  }
]

export function getStageStatus(
  presentation: ModelStagePresentation,
  assignment: ModelStageAssignment | undefined,
  currentProfile: ModelProfile | undefined
) {
  const profile = assignment?.modelProfile
  if (!profile) return { className: styles.warning, text: '未绑定模型 Profile' }
  if (!assignment?.agentRuntimeId) return { className: styles.warning, text: '未绑定 Agent 运行时' }
  if (!profile.enabled) return { className: styles.warning, text: '绑定的 Profile 已停用' }
  if (currentProfile?.lastConnectivityStatus !== 'SUCCESS') {
    return { className: styles.warning, text: '模型 Provider 尚未通过连通性测试' }
  }
  const probeResult = currentProfile.agentProbeResults.find(
    (result) => result.agentRuntimeId === assignment.agentRuntimeId
  )
  if (probeResult?.agentCompatible !== true) {
    return { className: styles.warning, text: '尚未通过 Agent 兼容性测试' }
  }
  return { className: styles.ready, text: presentation.readyText }
}

export function isActiveProbeStatus(status: ModelProfileAgentProbeRunStatus | undefined) {
  return status === 'PENDING' || status === 'RUNNING'
}

export function latestAgentProbeTime(results: ModelProfileAgentProbeResult[]) {
  const timestamps = results
    .map((result) => result.finishedAt ?? result.startedAt)
    .filter((value): value is string => Boolean(value))
    .map((value) => new Date(value).getTime())
    .filter(Number.isFinite)

  return timestamps.length ? new Date(Math.max(...timestamps)).toISOString() : null
}
