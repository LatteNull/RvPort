import { Position } from '@xyflow/react'
import { describe, expect, it } from 'vitest'

import { getFeedbackRoute, getWorkflowStepPath } from './routing'

describe('workflow edge routing', () => {
  it.each([0.000001, 0.5, 1])(
    'keeps the manual label on its horizontal segment with a %spx measured handle offset',
    (delta) => {
      const sourceX = 1168 + delta
      const targetX = 358 + delta
      const manual = getFeedbackRoute('manual-assets', sourceX, 592, targetX, 552)

      expect(manual.labelX).toBeCloseTo((sourceX + targetX) / 2)
      expect(sourceX - manual.labelX).toBeGreaterThan(70)
    }
  )

  it.each([36, 38, 40])('keeps a single vertical channel across a %ipx gap', (gap) => {
    const path = getWorkflowStepPath({
      sourceX: 0,
      sourceY: 0,
      sourcePosition: Position.Right,
      targetX: gap,
      targetY: 130,
      targetPosition: Position.Left
    })

    // 两个圆角分别属于出发和到达转弯，中间不再产生额外的折返圆角。
    expect(path.match(/Q/g)).toHaveLength(2)
    expect(path).toContain(`L${gap / 2} 65`)
  })

  it('separates feedback lanes below the groups and keeps labels clear of vertical edges', () => {
    const manual = getFeedbackRoute('manual-assets', 1168, 592, 358, 552)
    const optimize = getFeedbackRoute('optimize-assets', 1908, 422, 358, 552)

    expect(manual.laneY).toBeGreaterThan(642)
    expect(optimize.laneY - manual.laneY).toBeGreaterThanOrEqual(40)
    for (const route of [manual, optimize]) {
      for (const verticalX of [358, 1168, 1908]) {
        expect(Math.abs(route.labelX - verticalX)).toBeGreaterThan(70)
      }
    }
    expect(optimize.labelX).toBeGreaterThan(1168)
  })
})
