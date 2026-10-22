import { describe, expect, it } from 'vitest'

import { presentRiskEvidence } from './evidencePresentation'

describe('专项分析证据适配', () => {
  it('保留全部服务端步骤及顺序，按主要命中选择位置，不推断缺失说明', () => {
    const result = presentRiskEvidence({
      primaryOccurrenceId: 'second',
      occurrences: [
        { id: 'first' },
        { id: 'second', location: { file: 'a.cpp', span: { start: { line: 80 } } } }
      ],
      evidenceChain: {
        status: 'complete',
        primaryPath: ['b'],
        steps: [
          { id: 'a', kind: 'sourceObservation' },
          { id: 'b', kind: 'conclusion' }
        ]
      }
    })
    expect(result.defaultOccurrenceIndex).toBe(1)
    expect(result.model.evidencePath.steps.map((step) => step.id)).toEqual(['a', 'b'])
    expect(result.model.evidencePath.steps[0].title).toBeUndefined()
    expect(result.occurrences[1].location?.span?.start?.line).toBe(80)
  })
  it('读取证据自带的源码，过滤无效片段和行号', () => {
    const result = presentRiskEvidence({
      evidenceChain: {
        steps: [
          {
            source: {
              file: 'a.c',
              context: {
                lines: [
                  { line: 20, text: 'x();' },
                  { line: -1, text: 'invalid' }
                ],
                highlights: [{ line: 20, startColumn: 1, endColumn: 2 }]
              }
            }
          }
        ]
      }
    })
    expect(result.model.evidencePath.steps[0].source?.context?.lines).toEqual([
      { line: 20, text: 'x();' }
    ])
    expect(
      presentRiskEvidence({ evidenceChain: { steps: 'bad' }, occurrences: null }).model.evidencePath
        .steps
    ).toEqual([])
  })
})
