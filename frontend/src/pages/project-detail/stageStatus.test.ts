import { describe, expect, it } from 'vitest'

import {
  getStageStatusStyleVars,
  getStageStatusText,
  normalizeProjectPipelineStageStatus
} from './stageStatus'

describe('stageStatus', () => {
  it.each([
    ['DONE', 'done'],
    ['RUNNING', 'running'],
    ['BLOCKED', 'blocked'],
    ['PENDING', 'pending']
  ] as const)('normalizes %s to %s', (source, expected) => {
    expect(normalizeProjectPipelineStageStatus(source)).toBe(expected)
  })

  it('uses pending configuration when status is absent', () => {
    expect(normalizeProjectPipelineStageStatus()).toBe('pending')
    expect(getStageStatusText()).toBe('待处理')
    expect(getStageStatusStyleVars()).toMatchObject({
      '--stage-status-bar-bg': '#8a96a8'
    })
  })
})
