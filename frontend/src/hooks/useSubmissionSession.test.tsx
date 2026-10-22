import { StrictMode } from 'react'
import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { advanceAuthSession } from '@/store/authSession'

import { useSubmissionSession } from './useSubmissionSession'

const wrapper = ({ children }: { children: React.ReactNode }) => <StrictMode>{children}</StrictMode>

describe('submission ownership', () => {
  it('locks synchronously, unlocks on failure and permits a retry', async () => {
    const { result } = renderHook(() => useSubmissionSession('editor'), { wrapper })
    let reject!: (error: Error) => void
    const action = vi.fn(
      () =>
        new Promise<void>((_, no) => {
          reject = no
        })
    )
    let pending!: Promise<unknown>
    act(() => {
      pending = result.current.run(action).catch(() => undefined)
      void result.current.run(action)
    })
    expect(action).toHaveBeenCalledOnce()
    expect(result.current.busy).toBe(true)
    await act(async () => {
      reject(new Error('save failed'))
      await pending
    })
    expect(result.current.busy).toBe(false)
    await act(async () => {
      await result.current.run(async () => undefined)
    })
  })

  it.each(['switch', 'close', 'auth'])(
    'rejects late callbacks after %s without clearing the new lock',
    async (change) => {
      const { result, rerender } = renderHook(
        ({ key, active }) => useSubmissionSession(key, active),
        { initialProps: { key: 'A', active: true }, wrapper }
      )
      let finishOld!: () => void
      const applied = vi.fn()
      let old!: Promise<unknown>
      act(() => {
        old = result.current.run(async (isCurrent) => {
          await new Promise<void>((yes) => {
            finishOld = yes
          })
          if (isCurrent()) applied()
        })
      })
      if (change === 'auth') act(() => advanceAuthSession())
      else if (change === 'close') {
        rerender({ key: 'A', active: false })
        rerender({ key: 'A', active: true })
      } else rerender({ key: 'B', active: true })
      let finishNew!: () => void
      let next!: Promise<unknown>
      if (change !== 'auth')
        act(() => {
          next = result.current.run(
            () =>
              new Promise<void>((yes) => {
                finishNew = yes
              })
          )
        })
      await act(async () => {
        finishOld()
        await old
      })
      expect(applied).not.toHaveBeenCalled()
      if (change !== 'auth') {
        expect(result.current.busy).toBe(true)
        await act(async () => {
          finishNew()
          await next
        })
        expect(result.current.busy).toBe(false)
      }
    }
  )
  it('refuses an old callback invoked after a new editor is mounted', async () => {
    const { result, rerender } = renderHook(({ key }) => useSubmissionSession(key), {
      initialProps: { key: 'A' },
      wrapper
    })
    const oldRun = result.current.run
    rerender({ key: 'B' })
    const action = vi.fn(async () => undefined)
    await act(async () => {
      await oldRun(action)
    })
    expect(action).not.toHaveBeenCalled()
    expect(result.current.busy).toBe(false)
  })
})
