import { renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { usePageBounds } from './usePageBounds'

describe('page bounds', () => {
  it('waits for current completed data before correcting a page', () => {
    const onCorrectPage = vi.fn()
    const { rerender } = renderHook(
      ({ ready, total }) => usePageBounds({ page: 5, pageSize: 10, total, ready, onCorrectPage }),
      { initialProps: { ready: false, total: 25 } }
    )
    expect(onCorrectPage).not.toHaveBeenCalled()
    rerender({ ready: true, total: 25 })
    expect(onCorrectPage).toHaveBeenCalledExactlyOnceWith(3)
  })
  it('handles empty totals and ignores valid pages and invalid totals', () => {
    const onCorrectPage = vi.fn()
    const { rerender } = renderHook(
      ({ page, total }) => usePageBounds({ page, pageSize: 10, total, ready: true, onCorrectPage }),
      { initialProps: { page: 1, total: 0 } }
    )
    expect(onCorrectPage).not.toHaveBeenCalled()
    rerender({ page: 3, total: Number.NaN })
    rerender({ page: 3, total: -1 })
    expect(onCorrectPage).not.toHaveBeenCalled()
    rerender({ page: 3, total: 0 })
    expect(onCorrectPage).toHaveBeenCalledExactlyOnceWith(1)
  })
})
