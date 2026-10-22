import { describe, expect, it } from 'vitest'

import type { ProjectWorkflowStatus } from '@/types/project'

import { deriveWorkflowGatewayPresentation, deriveWorkflowPresentation } from './presentation'
import { workflowStages } from './topology'

function status(
  overrides: Record<string, ProjectWorkflowStatus['stages'][number]['status']>
): ProjectWorkflowStatus {
  return {
    activeEdgeIds: [],
    currentStageId: '',
    projectId: 'project-1',
    stages: workflowStages.map((stage) => ({
      id: stage.id,
      status: overrides[stage.id] ?? 'PENDING'
    })),
    updatedAt: '2026-09-10T00:00:00Z'
  }
}

describe('workflow presentation state', () => {
  it('marks a pending stage ready after every prerequisite is done', () => {
    const presentation = deriveWorkflowPresentation(
      status({ assets: 'DONE', env: 'DONE', project: 'DONE' })
    )

    expect(presentation.get('kb')).toMatchObject({
      assistStatus: 'WAITING',
      dependencyIds: ['x86-build']
    })
    expect(presentation.get('x86-build')).toMatchObject({ assistStatus: 'READY' })
  })

  it('lists unfinished direct prerequisites while a stage waits', () => {
    const presentation = deriveWorkflowPresentation(
      status({ assets: 'DONE', kb: 'DONE', project: 'DONE', 'rv-dependency-analysis': 'RUNNING' })
    )

    expect(presentation.get('report')).toMatchObject({
      assistStatus: 'WAITING',
      dependencyIds: ['rv-dependency-analysis']
    })
  })

  it('propagates an upstream block through pending descendants', () => {
    const presentation = deriveWorkflowPresentation(
      status({ assets: 'DONE', env: 'DONE', kb: 'DONE', project: 'DONE', 'x86-build': 'BLOCKED' })
    )

    expect(presentation.get('rv-dependency-analysis')).toMatchObject({
      assistStatus: 'BLOCKED',
      dependencyIds: ['x86-build']
    })
    expect(presentation.get('report')).toMatchObject({
      assistStatus: 'BLOCKED',
      dependencyIds: ['rv-dependency-analysis']
    })
    expect(presentation.get('archive')).toMatchObject({ assistStatus: 'BLOCKED' })
  })

  it('stops propagated blocking at a completed stage boundary', () => {
    const presentation = deriveWorkflowPresentation(
      status({ kb: 'BLOCKED', report: 'DONE', 'rv-dependency-analysis': 'DONE' })
    )

    expect(presentation.get('report')).toMatchObject({
      assistStatus: null,
      blockedByIds: [],
      flowBlocked: false,
      status: 'done'
    })
    expect(presentation.get('build')).toMatchObject({
      assistStatus: 'READY',
      blockedByIds: [],
      flowBlocked: false
    })
  })

  it('does not add an assist state after a stage enters its own lifecycle', () => {
    const presentation = deriveWorkflowPresentation(status({ project: 'DONE', report: 'RUNNING' }))

    expect(presentation.get('report')).toMatchObject({ assistStatus: null, status: 'running' })
  })

  it('does not treat feedback edges as required prerequisites', () => {
    const presentation = deriveWorkflowPresentation(status({ manual: 'BLOCKED', project: 'DONE' }))

    expect(presentation.get('assets')).toMatchObject({ assistStatus: 'READY' })
  })

  it('summarizes parallel report inputs at the gateway', () => {
    const gateway = deriveWorkflowGatewayPresentation(
      status({ assets: 'DONE', kb: 'DONE', project: 'DONE', 'rv-dependency-analysis': 'RUNNING' })
    ).get('report-inputs')

    expect(gateway).toEqual({ completed: 1, state: 'ACTIVE', total: 2 })
  })

  it('marks the gateway blocked when any input chain is blocked', () => {
    const gateway = deriveWorkflowGatewayPresentation(
      status({ kb: 'BLOCKED', report: 'DONE', 'rv-dependency-analysis': 'DONE' })
    ).get('report-inputs')

    expect(gateway).toEqual({ completed: 1, state: 'BLOCKED', total: 2 })
  })
})

describe('specialized analysis facts and report prerequisites', () => {
  it('keeps omitted specialized stages pending with real build blockers', () => {
    const workflowStatus = {
      projectId: 'p',
      currentStageId: 'x86-build',
      activeEdgeIds: [],
      updatedAt: '',
      stages: [
        { id: 'x86-build', status: 'BLOCKED' },
        { id: 'kb', status: 'PENDING' },
        { id: 'rv-dependency-analysis', status: 'PENDING' }
      ]
    } as ProjectWorkflowStatus
    const presentation = deriveWorkflowPresentation(workflowStatus)
    expect(presentation.get('memory-order-analysis')).toMatchObject({
      status: 'pending',
      flowBlocked: true
    })
    expect(presentation.get('floating-point-analysis')).toMatchObject({
      status: 'pending'
    })
    expect(deriveWorkflowGatewayPresentation(workflowStatus).get('report-inputs')).toMatchObject({
      completed: 0,
      total: 2,
      state: 'BLOCKED'
    })
  })
  it('uses the official backend stage fact', () => {
    const workflowStatus = {
      projectId: 'p',
      currentStageId: 'memory-order-analysis',
      activeEdgeIds: [],
      updatedAt: '',
      stages: [{ id: 'memory-order-analysis', status: 'RUNNING' }]
    } as ProjectWorkflowStatus
    expect(deriveWorkflowPresentation(workflowStatus).get('memory-order-analysis')).toMatchObject({
      status: 'running'
    })
  })
})
