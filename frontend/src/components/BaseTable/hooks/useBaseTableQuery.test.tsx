import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { expect, it, vi } from 'vitest'

import { createTestQueryClient } from '@/test/test-utils'

import { useBaseTableQuery } from './useBaseTableQuery'

it('retains rows for pagination but never reuses rows from another resource', async () => {
  const client = createTestQueryClient()
  const request = vi
    .fn()
    .mockResolvedValueOnce({
      items: [{ id: 'old' }],
      total: 40,
      page: 1,
      pageSize: 20,
      hasMore: true
    })
    .mockImplementation(() => new Promise(() => {}))
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  const { result, rerender } = renderHook(
    ({ resource }) =>
      useBaseTableQuery({ queryKey: ['rows', resource], initialPageSize: 20, request }),
    { wrapper, initialProps: { resource: 'first' } }
  )
  await waitFor(() => expect(result.current.displayedData?.items).toEqual([{ id: 'old' }]))
  act(() => result.current.updatePagination(2, 20))
  expect(result.current.displayedData?.items).toEqual([{ id: 'old' }])
  rerender({ resource: 'second' })
  expect(result.current.displayedData).toBeUndefined()
})
