import { describe, expect, it } from 'vitest'

import { getStageDrawerWidth, STAGE_DRAWER_WIDTH } from './drawerWidth'

describe('project stage drawer widths', () => {
  it.each(['project', 'env', 'assets', 'manual', undefined, 'unknown'])(
    'uses the standard width for %s',
    (stageId) => {
      expect(getStageDrawerWidth(stageId)).toBe(`min(${STAGE_DRAWER_WIDTH.standard}px, 100vw)`)
    }
  )

  it.each([
    'archive',
    'build',
    'kb',
    'optimize',
    'report',
    'rv-dependency-analysis',
    'test',
    'x86-build'
  ])('uses the wide width for %s', (stageId) => {
    expect(getStageDrawerWidth(stageId)).toBe(
      `min(${STAGE_DRAWER_WIDTH.wide}px, calc(100vw - 96px))`
    )
  })
})
