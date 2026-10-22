import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { expect, it, vi } from 'vitest'

import { createTestQueryClient } from '@/test/test-utils'

import { useModelProfiles } from './useModelProfiles'

const api = vi.hoisted(() => ({
  getModelProfiles: vi.fn(),
  getAgentRuntimes: vi.fn(),
  getModelStageAssignments: vi.fn(),
  getModelProfileAgentTestRun: vi.fn(),
  createModelProfile: vi.fn(),
  deleteModelProfile: vi.fn(),
  testModelProfileAgents: vi.fn(),
  testModelProfileConnectivity: vi.fn(),
  updateModelProfile: vi.fn(),
  updateModelStageAssignments: vi.fn()
}))
vi.mock('@/api/admin/models', () => api)

it('continues observing an active probe after its first detail request fails', async () => {
  vi.useFakeTimers()
  const client = createTestQueryClient()
  api.getModelProfiles.mockResolvedValue({
    items: [{ activeAgentProbeRun: { runId: 'probe-1', status: 'RUNNING' } }],
    total: 1,
    pageSize: 20,
    page: 1,
    hasMore: false
  })
  api.getAgentRuntimes.mockResolvedValue([])
  api.getModelStageAssignments.mockResolvedValue([])
  api.getModelProfileAgentTestRun
    .mockRejectedValueOnce(new Error('temporary failure'))
    .mockResolvedValue({ id: 'probe-1', status: 'RUNNING' })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  const { unmount } = renderHook(() => useModelProfiles({ current: null }), { wrapper })
  try {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50)
    })
    expect(api.getModelProfileAgentTestRun).toHaveBeenCalledOnce()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2100)
    })
    expect(api.getModelProfileAgentTestRun).toHaveBeenCalledTimes(2)
  } finally {
    unmount()
    client.clear()
    vi.useRealTimers()
  }
})
