import type { CSSProperties } from 'react'

import type { ProjectPipelineStageStatus } from '@/types/project'

import type { WorkflowStageStatus } from './Workflow/topology'

type StageStatusStyleVars = CSSProperties & {
  '--stage-status-bar-bg': string
  '--stage-status-tag-bg': string
  '--stage-status-tag-color': string
}

interface StageStatusConfig {
  text: string
  styleVars: StageStatusStyleVars
}

export const stageStatusConfig: Record<WorkflowStageStatus, StageStatusConfig> = {
  done: {
    text: '已完成',
    styleVars: {
      '--stage-status-bar-bg': '#1bb700',
      '--stage-status-tag-bg': '#1BB7001A',
      '--stage-status-tag-color': '#1BB700'
    }
  },
  running: {
    text: '进行中',
    styleVars: {
      '--stage-status-bar-bg': '#1f70ea',
      '--stage-status-tag-bg': '#1f70ea',
      '--stage-status-tag-color': '#ffffff'
    }
  },
  pending: {
    text: '待处理',
    styleVars: {
      '--stage-status-bar-bg': '#8a96a8',
      '--stage-status-tag-bg': '#c7c7c7',
      '--stage-status-tag-color': '#ffffff'
    }
  },
  blocked: {
    text: '阻塞',
    styleVars: {
      '--stage-status-bar-bg': '#ff3b30',
      '--stage-status-tag-bg': '#ff3b30',
      '--stage-status-tag-color': '#ffffff'
    }
  }
}

export const projectPipelineStageStatusMap: Record<
  ProjectPipelineStageStatus,
  WorkflowStageStatus
> = {
  DONE: 'done',
  RUNNING: 'running',
  BLOCKED: 'blocked',
  PENDING: 'pending'
}

export function normalizeProjectPipelineStageStatus(
  status?: ProjectPipelineStageStatus | WorkflowStageStatus
): WorkflowStageStatus {
  if (!status) {
    return 'pending'
  }

  if (status in projectPipelineStageStatusMap) {
    return projectPipelineStageStatusMap[status as ProjectPipelineStageStatus]
  }

  return status as WorkflowStageStatus
}

export function getStageStatusText(status?: WorkflowStageStatus) {
  return stageStatusConfig[status ?? 'pending'].text
}

export function getStageStatusStyleVars(status?: WorkflowStageStatus) {
  return stageStatusConfig[status ?? 'pending'].styleVars
}
