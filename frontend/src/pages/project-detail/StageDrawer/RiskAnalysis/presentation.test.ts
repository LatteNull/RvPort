import { describe, expect, it } from 'vitest'

import { finding } from './fixtures.test-support'
import { presentFinding } from './presentation'

describe('专项分析接口内容展示', () => {
  it('读取验证方案及分析依据，中文完成状态不覆盖人工确认要求', () => {
    const result = presentFinding({
      ...finding,
      confidence: 'medium',
      resultStatus: 'COMPLETE',
      detail: {
        conclusion: {
          evidenceOrigin: 'heuristic',
          validationPlan: {
            inputClasses: ['cancellation', 'ill-conditioned-order', 'long-sequence'],
            errorMetrics: ['absolute', 'relative', 'ulp'],
            repeatStrategy: 'repeat across order, vector width, and thread count',
            thresholdSource: 'project-policy'
          }
        }
      }
    })
    expect(result.confidence).toBe('中')
    expect(result.resultStatus).toBe('分析完成')
    expect(result.requiresHumanConfirmation).toBe(true)
    expect(result.evidenceOrigin).toBe('启发式规则')
    expect(result.validationPlan).toEqual([
      { label: '验证输入', value: '正负抵消、对顺序敏感的输入、长序列' },
      { label: '误差指标', value: '绝对误差、相对误差、ULP（末位单位误差）' },
      { label: '重复方式', value: '改变计算顺序、向量宽度和线程数，重复测试' },
      { label: '阈值来源', value: '项目策略' }
    ])
  })
  it('不为缺失数据生成方案或影响，保留数字置信度和未知值', () => {
    const empty = presentFinding({ ...finding, detail: {} })
    expect(empty.validationPlan).toEqual([])
    expect(empty.evidenceOrigin).toBe('')
    expect(empty.impact).toBe('')
    expect(empty.confidence).toBe('0.9')
    const custom = presentFinding({
      ...finding,
      resultStatus: 'CUSTOM',
      detail: {
        conclusion: { validationPlan: { inputClasses: ['custom', null, 2], errorMetrics: {} } }
      }
    })
    expect(custom.resultStatus).toBe('CUSTOM')
    expect(custom.validationPlan).toEqual([{ label: '验证输入', value: 'custom' }])
  })
})
