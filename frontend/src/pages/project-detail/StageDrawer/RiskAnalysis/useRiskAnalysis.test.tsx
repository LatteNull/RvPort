import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as api from '@/api/project/specialized-analysis'
import { getProjectStageReadiness } from '@/api/project/workflow'
import { createTestQueryClient } from '@/test/test-utils'

import { latest, readiness, run } from './fixtures.test-support'
import { useRiskAnalysis } from './useRiskAnalysis'

vi.mock('@/api/project/specialized-analysis')
vi.mock('@/api/project/workflow')

beforeEach(() => {
  vi.useFakeTimers()
  vi.resetAllMocks()
  vi.mocked(getProjectStageReadiness).mockResolvedValue(readiness)
  vi.mocked(api.getSpecializedAnalysisLatest).mockResolvedValue(latest())
})
afterEach(() => vi.useRealTimers())

function setup() {
  const client = createTestQueryClient()
  const hook = renderHook(() => useRiskAnalysis('project', 'memory-order-analysis', true), {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )
  })
  return {
    ...hook,
    client,
    dispose: () => {
      hook.unmount()
      client.clear()
    }
  }
}
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

describe('specialized analysis authoritative event refresh', () => {
  it('updates history through domain invalidation without polling current observers', async () => {
    vi.mocked(api.getSpecializedAnalysis)
      .mockResolvedValueOnce({ ...run, status: 'RUNNING' })
      .mockResolvedValue(run)
    const hook = setup()
    await advance(1)
    act(() => hook.result.current.selectRun(run.id))
    await advance(1)
    expect(hook.result.current.run?.status).toBe('RUNNING')
    await act(async () => {
      await hook.client.invalidateQueries({
        queryKey: ['project-specialized-analysis', 'project', 'memory-order-analysis']
      })
    })
    await advance(1)
    expect(hook.result.current.run?.status).toBe('COMPLETE_WITH_RISK')
    expect(api.getSpecializedAnalysis).toHaveBeenCalledTimes(2)
    await advance(6000)
    expect(api.getSpecializedAnalysis).toHaveBeenCalledTimes(2)
    hook.dispose()
  })
  it('keeps observing an execution before its result becomes available', async () => {
    vi.mocked(api.getSpecializedAnalysisLatest)
      .mockResolvedValueOnce({
        ...latest(null),
        execution: {
          id: 'execution',
          taskId: 'task',
          status: 'RUNNING',
          progress: 10,
          message: null,
          errorCode: null,
          errorMessage: null,
          createdAt: run.createdAt,
          startedAt: null,
          finishedAt: null
        }
      })
      .mockResolvedValue(latest())
    const hook = setup()
    await advance(1)
    expect(hook.result.current.active).toBe(true)
    expect(hook.result.current.run).toBeNull()
    await act(async () => {
      await hook.client.invalidateQueries({
        queryKey: ['project-specialized-analysis', 'project', 'memory-order-analysis']
      })
    })
    await advance(1)
    expect(hook.result.current.run?.id).toBe(run.id)
    expect(api.getSpecializedAnalysisLatest).toHaveBeenCalledTimes(2)
    hook.dispose()
  })
})
