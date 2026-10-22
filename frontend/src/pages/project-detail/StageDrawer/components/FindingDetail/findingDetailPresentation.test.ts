import { describe, expect, it } from 'vitest'

import type { ProjectKnowledgeBaseFindingDetail } from '@/types/project/knowledge-base'

import {
  getCompletionLabel,
  getFindingDetailModel,
  getFindingSourceLocation,
  getReachabilityLabel,
  getReasonCodeLabel
} from './findingDetailPresentation'

function createDetail(
  overrides: Partial<ProjectKnowledgeBaseFindingDetail> = {}
): ProjectKnowledgeBaseFindingDetail {
  return {
    category: 'x86_intrinsic',
    description: '使用了 x86 intrinsic',
    evidence: {},
    filePath: 'src/main.cpp',
    id: 'finding-1',
    lineEnd: 8,
    lineStart: 8,
    ruleId: 'rule-1',
    severity: 'high',
    status: 'DETECTED',
    suggestion: '替换为可移植实现',
    symbol: '_mm_add_ps',
    ...overrides
  }
}

describe('Finding detail presentation', () => {
  it('prefers top-level structured fields and selects the declared primary occurrence', () => {
    const detail = createDetail({
      conclusion: { status: 'complete', title: '顶层结论' },
      evidence: {
        finding: {
          conclusion: { title: '嵌套结论' },
          primaryOccurrenceId: 'occurrence-2'
        }
      },
      occurrences: [
        { id: 'occurrence-1', location: { file: 'src/one.cpp' } },
        { id: 'occurrence-2', location: { file: 'src/two.cpp' } }
      ]
    })

    const model = getFindingDetailModel(detail)

    expect(model.conclusion.title).toBe('顶层结论')
    expect(model.primaryOccurrenceId).toBe('occurrence-2')
    expect(model.defaultOccurrenceId).toBe('occurrence-2')
    expect(model.defaultOccurrenceIndex).toBe(1)
  })

  it('falls back to nested V2 fields and the first occurrence with a source location', () => {
    const detail = createDetail({
      evidence: {
        finding: {
          conclusion: { status: 'partial', title: '兼容结论' },
          fact: { kind: 'build_argument' },
          occurrences: [
            { id: 'empty-location' },
            { id: 'located', location: { file: 'CMakeLists.txt' } }
          ]
        }
      },
      filePath: null,
      lineEnd: null,
      lineStart: null
    })

    const model = getFindingDetailModel(detail)

    expect(model.conclusion.title).toBe('兼容结论')
    expect(model.fact.kind).toBe('build_argument')
    expect(model.defaultOccurrenceId).toBe('located')
    expect(model.defaultOccurrenceIndex).toBe(1)
  })

  it('preserves every backend step in response order regardless of primary path completeness', () => {
    const complete = getFindingDetailModel(
      createDetail({
        evidenceChain: {
          primaryPath: ['source', 'assessment'],
          steps: [{ id: 'assessment' }, { id: 'extra' }, { id: 'source' }]
        }
      })
    )
    const incomplete = getFindingDetailModel(
      createDetail({
        evidenceChain: {
          breaks: [{ id: 'break-1', reasonCode: 'missing_input', stage: 'selection' }],
          budget: { truncated: true },
          primaryPath: ['source', 'missing'],
          steps: [{ id: 'source' }, { id: 'candidate' }]
        }
      })
    )

    expect(complete.evidencePath.steps.map((step) => step.id)).toEqual([
      'assessment',
      'extra',
      'source'
    ])
    expect(incomplete.evidencePath.steps.map((step) => step.id)).toEqual(['source', 'candidate'])
    expect(incomplete.evidenceChain.breaks).toHaveLength(1)
    expect(incomplete.evidenceChain.budget?.truncated).toBe(true)
  })

  it('projects the legacy source location and localizes known states without hiding unknown ones', () => {
    const detail = createDetail()
    const model = getFindingDetailModel(detail)

    expect(getFindingSourceLocation(detail, model)).toEqual({
      file: 'src/main.cpp',
      span: { end: { line: 8 }, start: { line: 8 } }
    })
    expect(getCompletionLabel('ambiguous')).toBe('存在歧义')
    expect(getReachabilityLabel('not_selected')).toBe('当前目标未选中')
    expect(getReasonCodeLabel('missing_input')).toBe('缺少完成判断所需的输入')
    expect(getReasonCodeLabel('future_reason')).toBe('future_reason')
  })
})
