import { type ReactNode, useState } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { type BackendProject, getProject, updateProject } from '@/api/project/projects'
import { advanceAuthSession } from '@/store/authSession'
import { createTestQueryClient } from '@/test/test-utils'
import { feedback } from '@/utils/feedback'

import { useProjectDrawer } from './useProjectDrawer'

vi.mock('@/api/project/projects', () => ({ getProject: vi.fn(), updateProject: vi.fn() }))
vi.mock('@/utils/feedback', () => ({ feedback: { success: vi.fn() } }))

function Wrapper({ children }: { children: ReactNode }) {
  const [client] = useState(createTestQueryClient)
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

describe('project submission ownership', () => {
  it.each(['auth', 'project', 'close'])(
    'does not submit old validation after %s changes',
    async (change) => {
      vi.mocked(getProject).mockResolvedValue({ id: 'A' } as BackendProject)
      const { result, rerender } = renderHook(({ id, visible }) => useProjectDrawer(id, visible), {
        initialProps: { id: 'A', visible: true },
        wrapper: Wrapper
      })
      let finish!: (value: { description: string }) => void
      vi.spyOn(result.current.form, 'validateFields').mockImplementation(
        () =>
          new Promise((resolve) => {
            finish = resolve
          })
      )
      let pending!: Promise<unknown>
      act(() => {
        pending = result.current.handleSave()
        void result.current.handleSave()
      })
      expect(result.current.isSaving).toBe(true)
      act(() => {
        if (change === 'auth') advanceAuthSession()
        else rerender({ id: change === 'project' ? 'B' : 'A', visible: change !== 'close' })
      })
      await act(async () => {
        finish({ description: 'old draft' })
        await pending
      })
      expect(updateProject).not.toHaveBeenCalled()
      expect(feedback.success).not.toHaveBeenCalled()
    }
  )
  it('preserves the draft and releases the validation lock for retry', async () => {
    vi.mocked(getProject).mockResolvedValue({ id: 'A' } as BackendProject)
    vi.mocked(updateProject).mockResolvedValue({ id: 'A', description: 'draft' } as BackendProject)
    const { result } = renderHook(() => useProjectDrawer('A', true), { wrapper: Wrapper })
    act(() => {
      result.current.form.setFieldValue('description', 'draft')
      result.current.setIsDescriptionEditing(true)
    })
    vi.spyOn(result.current.form, 'validateFields')
      .mockRejectedValueOnce(new Error('invalid'))
      .mockResolvedValueOnce({ description: 'draft' })
    await act(async () => {
      await expect(result.current.handleSave()).rejects.toThrow('invalid')
    })
    expect(result.current.isSaving).toBe(false)
    expect(result.current.form.getFieldValue('description')).toBe('draft')
    expect(result.current.isDescriptionEditing).toBe(true)
    await act(async () => {
      await result.current.handleSave()
    })
    expect(updateProject).toHaveBeenCalledOnce()
    expect(result.current.isDescriptionEditing).toBe(false)
  })
  it('does not reset a reopened editor when an old save finishes', async () => {
    vi.mocked(getProject).mockResolvedValue({ id: 'A' } as BackendProject)
    let finish!: (value: BackendProject) => void
    vi.mocked(updateProject).mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve
        })
    )
    const { result, rerender } = renderHook(({ visible }) => useProjectDrawer('A', visible), {
      initialProps: { visible: true },
      wrapper: Wrapper
    })
    vi.spyOn(result.current.form, 'validateFields').mockResolvedValue({ description: 'old' })
    let pending!: Promise<unknown>
    await act(async () => {
      pending = result.current.handleSave()
      await Promise.resolve()
    })
    rerender({ visible: false })
    rerender({ visible: true })
    act(() => {
      result.current.form.setFieldValue('description', 'new')
      result.current.setIsDescriptionEditing(true)
    })
    await act(async () => {
      finish({ id: 'A', description: 'old' } as BackendProject)
      await pending
    })
    expect(result.current.form.getFieldValue('description')).toBe('new')
    expect(result.current.isDescriptionEditing).toBe(true)
    expect(feedback.success).not.toHaveBeenCalled()
  })
})
