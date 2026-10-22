import type { ProjectWorkflowStatus } from '@/types/project'

import { normalizeProjectPipelineStageStatus } from '../stageStatus'
import { workflowGateways, workflowStages, type WorkflowStageStatus } from './topology'

export type WorkflowAssistStatus = 'READY' | 'WAITING' | 'BLOCKED'

export interface WorkflowStagePresentation {
  assistStatus: WorkflowAssistStatus | null
  blockedByIds: string[]
  dependencyIds: string[]
  flowBlocked: boolean
  status: WorkflowStageStatus
}

type DependencyState = 'BLOCKED' | 'INCOMPLETE' | 'COMPLETED'

export type WorkflowGatewayState = 'ACTIVE' | 'BLOCKED' | 'COMPLETE' | 'WAITING'

export interface WorkflowGatewayPresentation {
  completed: number
  state: WorkflowGatewayState
  total: number
}

export function deriveWorkflowPresentation(workflowStatus?: ProjectWorkflowStatus) {
  const statusByStageId = new Map(workflowStatus?.stages.map((stage) => [stage.id, stage.status]))
  const presentationByStageId = new Map<string, WorkflowStagePresentation>()

  // 前置节点在拓扑中始终先于目标节点，因此可在单次正向遍历中完成阻塞传播。
  for (const stage of workflowStages) {
    const status = workflowStatus
      ? normalizeProjectPipelineStageStatus(statusByStageId.get(stage.id))
      : stage.status
    const dependencies = stage.prerequisiteIds
      .map((stageId) => presentationByStageId.get(stageId))
      .filter((item): item is WorkflowStagePresentation => Boolean(item))
    const blockedByIds = Array.from(
      new Set(
        status === 'blocked'
          ? [stage.id]
          : status === 'pending'
            ? dependencies.flatMap((dependency, index) => {
                if (!dependency.flowBlocked) return []
                return dependency.blockedByIds.length > 0
                  ? dependency.blockedByIds
                  : [stage.prerequisiteIds[index]]
              })
            : []
      )
    )
    // 已进入执行或完成生命周期的节点是事实边界，不被后续重新扫描失败追溯染色。
    const flowBlocked = status === 'blocked' || (status === 'pending' && blockedByIds.length > 0)

    if (status !== 'pending' || dependencies.length === 0) {
      presentationByStageId.set(stage.id, {
        assistStatus: null,
        blockedByIds,
        dependencyIds: [],
        flowBlocked,
        status
      })
      continue
    }

    const blockedDependencyIds = stage.prerequisiteIds.filter((_, index) => {
      const dependency = dependencies[index]
      return dependency?.flowBlocked
    })
    const incompleteDependencyIds = stage.prerequisiteIds.filter(
      (_, index) => dependencies[index]?.status !== 'done'
    )
    const dependencyState: DependencyState =
      blockedDependencyIds.length > 0
        ? 'BLOCKED'
        : incompleteDependencyIds.length > 0
          ? 'INCOMPLETE'
          : 'COMPLETED'

    switch (dependencyState) {
      case 'BLOCKED':
        presentationByStageId.set(stage.id, {
          assistStatus: 'BLOCKED',
          blockedByIds,
          dependencyIds: blockedDependencyIds,
          flowBlocked,
          status
        })
        break
      case 'INCOMPLETE':
        presentationByStageId.set(stage.id, {
          assistStatus: 'WAITING',
          blockedByIds,
          dependencyIds: incompleteDependencyIds,
          flowBlocked,
          status
        })
        break
      case 'COMPLETED':
        presentationByStageId.set(stage.id, {
          assistStatus: 'READY',
          blockedByIds,
          dependencyIds: [],
          flowBlocked,
          status
        })
        break
    }
  }

  return presentationByStageId
}

export function deriveWorkflowGatewayPresentation(workflowStatus?: ProjectWorkflowStatus) {
  const stagePresentation = deriveWorkflowPresentation(workflowStatus)
  const gatewayPresentation = new Map<string, WorkflowGatewayPresentation>()

  for (const gateway of workflowGateways) {
    const dependencies = gateway.prerequisiteIds
      .map((stageId) => stagePresentation.get(stageId))
      .filter((item): item is WorkflowStagePresentation => Boolean(item))
    const completed = dependencies.filter(
      (dependency) => dependency.status === 'done' && !dependency.flowBlocked
    ).length
    let state: WorkflowGatewayState

    if (dependencies.some((dependency) => dependency.flowBlocked)) {
      state = 'BLOCKED'
    } else if (completed === dependencies.length) {
      state = 'COMPLETE'
    } else if (dependencies.some((dependency) => dependency.status === 'running')) {
      state = 'ACTIVE'
    } else {
      state = 'WAITING'
    }

    gatewayPresentation.set(gateway.id, {
      completed,
      state,
      total: gateway.prerequisiteIds.length
    })
  }

  return gatewayPresentation
}

export function getWorkflowAssistText(assistStatus: WorkflowAssistStatus, dependencyIds: string[]) {
  const dependencyTitles = dependencyIds
    .map((stageId) => workflowStages.find((stage) => stage.id === stageId)?.title)
    .filter((title): title is string => Boolean(title))
    .join('、')

  switch (assistStatus) {
    case 'READY':
      return '前置阶段已完成，可以开始'
    case 'WAITING':
      return dependencyTitles ? `等待：${dependencyTitles}` : '等待前置阶段完成'
    case 'BLOCKED':
      return dependencyTitles ? `阻塞：${dependencyTitles}` : '前置阶段已阻塞'
  }
}

const reasonTextByCode: Record<string, string> = {
  ACTIVE_SOURCE_MISSING: '尚未配置当前源码',
  BUILD_VALIDATION_FAILED: '构建验证失败',
  DEPENDENCY_ANALYSIS_FAILED: '依赖分析失败',
  ENVIRONMENT_TEST_FAILED: '环境检查失败',
  ENVIRONMENT_TEST_REQUIRED: '需要先完成环境检查',
  KB_SCAN_FAILED: '知识库扫描失败',
  RUNTIME_ENVIRONMENTS_INCOMPLETE: '运行环境尚未配置完整',
  X86_BUILD_FAILED: 'x86 构建失败'
}

function stageTitles(stageIds: string[]) {
  return stageIds
    .map((stageId) => workflowStages.find((stage) => stage.id === stageId)?.title)
    .filter((title): title is string => Boolean(title))
    .join('、')
}

export function getWorkflowNodeHint(
  stageId: string,
  presentation: WorkflowStagePresentation,
  reasonCode?: string
) {
  if (presentation.status === 'done') {
    return '已完成'
  }

  if (presentation.status === 'running') {
    return '正在执行'
  }

  if (presentation.flowBlocked) {
    if (presentation.status === 'blocked') {
      return reasonTextByCode[reasonCode ?? ''] ?? '阶段执行失败'
    }
    const blockers = stageTitles(presentation.blockedByIds.filter((id) => id !== stageId))
    return blockers ? `受 ${blockers} 阻塞` : '当前流程已阻塞'
  }

  switch (presentation.status) {
    case 'blocked':
      return reasonTextByCode[reasonCode ?? ''] ?? '阶段执行失败'
    case 'pending': {
      const dependencies = stageTitles(presentation.dependencyIds)

      switch (presentation.assistStatus) {
        case 'READY':
          return '可以开始'
        case 'WAITING':
          return dependencies ? `等待 ${dependencies}` : '等待前置阶段'
        case 'BLOCKED':
          return dependencies ? `受 ${dependencies} 阻塞` : '当前流程已阻塞'
        default:
          return '待处理'
      }
    }
  }
}
