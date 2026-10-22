import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useProjectViewTransition } from './useProjectViewTransition'

const originalStartViewTransition = Object.getOwnPropertyDescriptor(document, 'startViewTransition')
const originalMatchMedia = Object.getOwnPropertyDescriptor(window, 'matchMedia')

afterEach(() => {
  if (originalStartViewTransition) {
    Object.defineProperty(document, 'startViewTransition', originalStartViewTransition)
  } else {
    Reflect.deleteProperty(document, 'startViewTransition')
  }
  if (originalMatchMedia) {
    Object.defineProperty(window, 'matchMedia', originalMatchMedia)
  } else {
    Reflect.deleteProperty(window, 'matchMedia')
  }
  delete document.documentElement.dataset.projectViewTransition
})

describe('useProjectViewTransition', () => {
  it('interrupts an in-flight view switch and keeps only the latest direction', async () => {
    const finish: Array<() => void> = []
    const skipTransition = vi.fn()
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      value: () => ({ matches: false })
    })
    Object.defineProperty(document, 'startViewTransition', {
      configurable: true,
      value: vi.fn((update: () => void) => {
        update()
        return {
          finished: new Promise<void>((resolve) => finish.push(resolve)),
          skipTransition
        }
      })
    })
    const navigateView = vi.fn()
    const { result } = renderHook(() => useProjectViewTransition())

    act(() => result.current('steps', navigateView))
    expect(document.documentElement.dataset.projectViewTransition).toBe('steps')
    act(() => result.current('workflow', navigateView))
    expect(skipTransition).toHaveBeenCalledTimes(1)
    expect(document.documentElement.dataset.projectViewTransition).toBe('workflow')
    expect(navigateView).toHaveBeenCalledWith({ flushSync: true, viewTransition: false })

    await act(async () => finish[0]())
    expect(document.documentElement.dataset.projectViewTransition).toBe('workflow')
    await act(async () => finish[1]())
    expect(document.documentElement.dataset.projectViewTransition).toBeUndefined()
  })

  it('switches immediately when reduced motion is requested', () => {
    const startViewTransition = vi.fn()
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      value: () => ({ matches: true })
    })
    Object.defineProperty(document, 'startViewTransition', {
      configurable: true,
      value: startViewTransition
    })
    const navigateView = vi.fn()
    const { result } = renderHook(() => useProjectViewTransition())

    act(() => result.current('steps', navigateView))
    expect(startViewTransition).not.toHaveBeenCalled()
    expect(navigateView).toHaveBeenCalledWith({ flushSync: true, viewTransition: false })
    expect(document.documentElement.dataset.projectViewTransition).toBeUndefined()
  })
})
