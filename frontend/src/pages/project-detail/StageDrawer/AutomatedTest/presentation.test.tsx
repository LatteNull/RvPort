import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { ProjectTestComparison } from '@/types/project'

import { getComparisonPresentation, renderComparisonStatusTag } from './presentation'

describe('automated test comparison presentation', () => {
  it.each([
    ['EQUIVALENT', '结果等价', '双端测试结果等价', 'success'],
    ['DIFFERENT_ACCEPTABLE', '差异可接受', '双端测试结果存在可接受差异', 'warning'],
    ['DIFFERENT_BLOCKING', '阻断性差异', '双端测试结果存在阻断性差异', 'error'],
    ['INCONCLUSIVE', '暂无法判断', '暂无法得出一致性结论', 'neutral']
  ])('maps backend status %s to Chinese presentation', (status, label, headline, tone) => {
    const comparison = {
      overallStatus: status,
      status: 'SUCCEEDED'
    } as ProjectTestComparison

    expect(renderToStaticMarkup(renderComparisonStatusTag(status))).toContain(label)
    expect(getComparisonPresentation(comparison)).toMatchObject({ headline, tone })
  })
})
