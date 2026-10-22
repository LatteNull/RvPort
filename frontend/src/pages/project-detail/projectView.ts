import { WORKFLOW_STAGE_IDS, type WorkflowStageId } from './Workflow/topology'

const workflowStageIds = new Set<string>(WORKFLOW_STAGE_IDS)

export function isProjectStageId(value: string): value is WorkflowStageId {
  return workflowStageIds.has(value)
}

export type ProjectView = 'workflow' | 'steps'

export interface ProjectViewLocation {
  view: ProjectView
  stageId?: WorkflowStageId
  valid: boolean
}

export function resolveProjectView(path?: string): ProjectViewLocation {
  const segments = path?.split('/').filter(Boolean) ?? []

  if (segments.length === 1 && segments[0] === 'workflow') {
    return { view: 'workflow', valid: true }
  }
  if (segments.length === 2 && isProjectStageId(segments[1])) {
    if (segments[0] === 'workflow') {
      return { view: 'workflow', stageId: segments[1], valid: true }
    }
    if (segments[0] === 'steps') {
      return { view: 'steps', stageId: segments[1], valid: true }
    }
  }

  return { view: 'workflow', valid: false }
}

export function projectViewPath(projectId: string, view: ProjectView, stageId?: WorkflowStageId) {
  const base = `/projects/${encodeURIComponent(projectId)}`
  return `${base}/${view}${stageId ? `/${stageId}` : ''}`
}
