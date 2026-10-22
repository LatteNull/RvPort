import { describe, expect, it, vi } from 'vitest'

import { advanceAuthSession } from '@/store/authSession'

import { readAllPages } from './readAllPages'

const page = (number: number, size: number, total: number) => ({
  items: [number],
  page: number,
  pageSize: size,
  total,
  hasMore: number * size < total
})
describe('complete paginated reads', () => {
  it('includes records beyond the first page and honors the actual server page size', async () => {
    const fetch = vi.fn(async (number: number) => page(number, 100, 250))
    const result = await readAllPages(fetch)
    expect(result.items).toEqual([1, 2, 3])
    expect(fetch).toHaveBeenLastCalledWith(3, 100)
  })
  it('limits page concurrency and preserves page ordering', async () => {
    let active = 0,
      peak = 0
    const result = await readAllPages(async (number) => {
      active++
      peak = Math.max(peak, active)
      await Promise.resolve()
      active--
      return page(number, 1, 11)
    })
    expect(result.items).toEqual(Array.from({ length: 11 }, (_, i) => i + 1))
    expect(peak).toBeLessThanOrEqual(4)
  })
  it.each(['auth', 'abort'])('does not fetch remaining pages after %s changes', async (change) => {
    const controller = new AbortController()
    const fetch = vi.fn(async () => {
      if (change === 'auth') advanceAuthSession()
      else controller.abort()
      return page(1, 100, 250)
    })
    await expect(readAllPages(fetch, { signal: controller.signal })).rejects.toBeInstanceOf(Error)
    expect(fetch).toHaveBeenCalledOnce()
  })
})
