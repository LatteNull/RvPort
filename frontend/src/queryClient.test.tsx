import { useQuery } from '@tanstack/react-query'
import { act, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { createTestQueryClient, renderWithQueryClient } from '@/test/test-utils'

import { isolateAuthQueries } from './queryClient'
import { useAuthStore } from './store/authStore'

function Table({ request }: { request: () => Promise<string> }) {
  const query = useQuery({ queryKey: ['project', 'same-filter'], queryFn: request })
  return <p>{query.data ?? 'loading'}</p>
}

describe('private cache isolation', () => {
  it('removes A data and late reads before B opens the same key while preserving public data', async () => {
    const client = createTestQueryClient()
    const stop = isolateAuthQueries(client)
    client.setQueryDefaults(['public'], { meta: { public: true } })
    client.setQueryData(['public'], 'public-data')
    const request = vi.fn().mockResolvedValueOnce('A secret').mockResolvedValueOnce('B data')
    const first = renderWithQueryClient(<Table request={request} />, client)
    await screen.findByText('A secret')
    first.unmount()
    let resolve!: (value: string) => void
    const late = client
      .fetchQuery({
        queryKey: ['late'],
        queryFn: () =>
          new Promise<string>((yes) => {
            resolve = yes
          })
      })
      .catch(() => null)
    act(() => useAuthStore.getState().logout())
    expect(client.getQueryData(['project', 'same-filter'])).toBeUndefined()
    expect(client.getQueryData(['public'])).toBe('public-data')
    resolve('old result')
    await late
    expect(client.getQueryData(['late'])).toBeUndefined()
    renderWithQueryClient(<Table request={request} />, client)
    expect(screen.queryByText('A secret')).not.toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('B data')).toBeInTheDocument())
    stop()
    client.clear()
  })
})
