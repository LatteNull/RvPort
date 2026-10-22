import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { useStageDraft } from './useStageDraft'

describe('stage draft reporting', () => {
  it('does not treat the previous submission as clean in a new editing session', () => {
    const { result, rerender } = renderHook(
      ({ scope }) => useStageDraft({ scope }, { scope: './' }, true),
      { initialProps: { scope: 'src/' } }
    )
    act(result.current.markSubmitted)
    expect(result.current.dirty).toBe(false)
    act(result.current.resetSubmitted)
    rerender({ scope: './' })
    expect(result.current.dirty).toBe(false)
    rerender({ scope: 'src/' })
    expect(result.current.dirty).toBe(true)
  })

  it('reports edits, reversions, visibility and unmount without treating defaults as dirty', () => {
    const report = vi.fn()
    const { result, rerender, unmount } = renderHook(
      ({ command, enabled }) => useStageDraft({ command }, { command: 'make' }, enabled, report),
      { initialProps: { command: 'make', enabled: true } }
    )
    expect(report).toHaveBeenLastCalledWith(false)
    rerender({ command: 'make -j', enabled: true })
    expect(result.current.dirty).toBe(true)
    expect(report).toHaveBeenLastCalledWith(true)
    rerender({ command: 'make', enabled: true })
    expect(result.current.dirty).toBe(false)
    rerender({ command: 'make -j', enabled: false })
    expect(report).toHaveBeenLastCalledWith(false)
    unmount()
    expect(report).toHaveBeenLastCalledWith(false)
  })

  it('clears only the successfully submitted snapshot and retains edits during a request', () => {
    const report = vi.fn()
    const { result, rerender } = renderHook(
      ({ command }) => useStageDraft({ command }, { command: 'make' }, true, report),
      { initialProps: { command: 'make -j' } }
    )
    const markSubmitted = result.current.markSubmitted
    rerender({ command: 'make -j8' })
    act(markSubmitted)
    expect(result.current.dirty).toBe(true)
    act(result.current.markSubmitted)
    expect(result.current.dirty).toBe(false)
    rerender({ command: 'make -j16' })
    expect(result.current.dirty).toBe(true)
  })
})
