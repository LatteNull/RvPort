import { describe, expect, it } from 'vitest'

import { projectViewPath, resolveProjectView } from './projectView'
import { WORKFLOW_STAGE_IDS } from './Workflow/topology'

describe('projectView', () => {
  it('resolves the workflow overview, drawer, and every stage step path', () => {
    expect(resolveProjectView('workflow')).toEqual({ view: 'workflow', valid: true })
    expect(resolveProjectView('workflow/assets')).toEqual({
      view: 'workflow',
      stageId: 'assets',
      valid: true
    })
    expect(resolveProjectView('steps/env')).toEqual({
      view: 'steps',
      stageId: 'env',
      valid: true
    })
    expect(resolveProjectView('steps/report')).toEqual({
      view: 'steps',
      stageId: 'report',
      valid: true
    })
  })

  it('rejects unavailable stages', () => {
    expect(resolveProjectView('workflow/unknown').valid).toBe(false)
    expect(resolveProjectView('steps/unknown').valid).toBe(false)
  })

  it('accepts a Step deep link for each Workflow stage', () => {
    for (const stageId of WORKFLOW_STAGE_IDS) {
      expect(resolveProjectView(`steps/${stageId}`)).toEqual({
        view: 'steps',
        stageId,
        valid: true
      })
    }
  })

  it('builds shareable view paths', () => {
    expect(projectViewPath('project-1', 'workflow')).toBe('/projects/project-1/workflow')
    expect(projectViewPath('project-1', 'workflow', 'assets')).toBe(
      '/projects/project-1/workflow/assets'
    )
    expect(projectViewPath('project-1', 'steps', 'env')).toBe('/projects/project-1/steps/env')
    expect(projectViewPath('project-1', 'steps', 'report')).toBe('/projects/project-1/steps/report')
  })
})
