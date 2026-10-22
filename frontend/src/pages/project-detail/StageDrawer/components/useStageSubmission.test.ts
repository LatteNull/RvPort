import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { useStageSubmission } from './useStageSubmission'

describe('提交受理到权威执行更新之间的状态', () => {
  it('仅在原上下文及原执行身份下保持待同步', () => {
    const { result, rerender } = renderHook(({ id, context }) => useStageSubmission(id, context), {
      initialProps: { id: 'old', context: 'project:source:1' }
    })
    expect(result.current.pending).toBe(false)
    act(() => result.current.markSubmitted())
    expect(result.current.pending).toBe(true)
    rerender({ id: 'new', context: 'project:source:1' })
    expect(result.current.pending).toBe(false)
    act(() => result.current.markSubmitted())
    rerender({ id: 'new', context: 'project:source:2' })
    expect(result.current.pending).toBe(false)
  })
})
