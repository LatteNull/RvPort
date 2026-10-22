import { type ReactNode, useState } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { createProjectKnowledgeBaseScan } from '@/api/project/knowledge-base'
import { advanceAuthSession } from '@/store/authSession'
import { createTestQueryClient } from '@/test/test-utils'
import { feedback } from '@/utils/feedback'

import { initialScanConfig } from './types'
import { useKnowledgeBaseDrawer } from './useKnowledgeBaseDrawer'

vi.mock('@/api/project/knowledge-base', async (original) => ({
  ...(await original<typeof import('@/api/project/knowledge-base')>()),
  createProjectKnowledgeBaseScan: vi.fn(),
  getProjectKnowledgeBaseScanLatest: async () => ({
    freshness: 'EMPTY',
    result: null,
    execution: null,
    context: { sourceRevisionId: 'source', runtimeEnvironmentVersion: 1 }
  })
}))
vi.mock('@/api/project/workflow', () => ({
  getProjectStageReadiness: async () => ({
    context: { sourceRevisionId: 'source', runtimeEnvironmentVersion: 1 },
    prerequisites: [
      { key: 'ACTIVE_SOURCE', status: 'SATISFIED' },
      { key: 'X86_BUILD', status: 'SATISFIED' }
    ]
  })
}))
vi.mock('@/utils/feedback', () => ({ feedback: { success: vi.fn(), error: vi.fn() } }))

function Wrapper({ children }: { children: ReactNode }) {
  const [client] = useState(createTestQueryClient)
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

describe('knowledge base validation ownership', () => {
  it.each(['auth', 'project', 'close', 'view'])(
    'does not create a scan after %s changes during validation',
    async (change) => {
      const { result, rerender } = renderHook(
        ({ project, visible }) => useKnowledgeBaseDrawer(project, visible),
        { initialProps: { project: 'A', visible: true }, wrapper: Wrapper }
      )
      act(() => result.current.showConfig())
      await waitFor(() => expect(result.current.x86BuildReady).toBe(true))
      let finish!: (value: typeof initialScanConfig) => void
      vi.spyOn(result.current.form, 'validateFields').mockImplementation(
        () =>
          new Promise((resolve) => {
            finish = resolve
          })
      )
      let pending!: Promise<unknown>
      act(() => {
        pending = result.current.handleCreateScan()
        void result.current.handleCreateScan()
      })
      expect(result.current.isCreating).toBe(true)
      act(() => {
        if (change === 'auth') advanceAuthSession()
        else if (change === 'view') result.current.showResults()
        else rerender({ project: change === 'project' ? 'B' : 'A', visible: change !== 'close' })
      })
      await act(async () => {
        finish(initialScanConfig)
        await pending
      })
      expect(createProjectKnowledgeBaseScan).not.toHaveBeenCalled()
      expect(feedback.success).not.toHaveBeenCalled()
    }
  )
  it('preserves the draft and unlocks when creation fails', async () => {
    vi.mocked(createProjectKnowledgeBaseScan).mockRejectedValue(new Error('unavailable'))
    const { result } = renderHook(() => useKnowledgeBaseDrawer('A', true), { wrapper: Wrapper })
    act(() => {
      result.current.showConfig()
      result.current.form.setFieldsValue({ ...initialScanConfig, scope: 'draft' })
    })
    await waitFor(() => expect(result.current.x86BuildReady).toBe(true))
    await act(async () => {
      await result.current.handleCreateScan()
    })
    expect(result.current.form.getFieldValue('scope')).toBe('draft')
    expect(result.current.isCreating).toBe(false)
    expect(result.current.view.type).toBe('config')
  })
})
