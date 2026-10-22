import { useState } from 'react'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import TableViewStateProvider from '../BaseTable/TableViewStateProvider'
import DebouncedSearchInput from '.'

function DraftHarness({
  dataset = 'list-1',
  active = true,
  resetKey = 0
}: {
  dataset?: string
  active?: boolean
  resetKey?: number
}) {
  const [detail, setDetail] = useState(false)
  return (
    <TableViewStateProvider active={active}>
      <button onClick={() => setDetail((v) => !v)}>切换详情</button>
      {detail ? (
        <p>详情</p>
      ) : (
        <DebouncedSearchInput
          aria-label="搜索"
          draftStateKey={['search-draft', dataset]}
          resetKey={resetKey}
          onSearch={searchSpy}
        />
      )}
    </TableViewStateProvider>
  )
}
const searchSpy = vi.fn()

describe('DebouncedSearchInput', () => {
  it('explicitly resets an unapplied draft even when the external value remains empty', () => {
    vi.useFakeTimers()
    searchSpy.mockClear()
    const { rerender } = render(<DraftHarness />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'stale' } })
    rerender(<DraftHarness resetKey={1} />)
    expect(screen.getByRole('textbox')).toHaveValue('')
    act(() => vi.advanceTimersByTime(1000))
    expect(searchSpy).not.toHaveBeenCalled()
    fireEvent.click(screen.getByText('切换详情'))
    fireEvent.click(screen.getByText('切换详情'))
    expect(screen.getByRole('textbox')).toHaveValue('')
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'fresh' } })
    fireEvent.click(screen.getByText('切换详情'))
    fireEvent.click(screen.getByText('切换详情'))
    expect(screen.getByRole('textbox')).toHaveValue('fresh')
    act(() => vi.advanceTimersByTime(300))
    expect(searchSpy).toHaveBeenCalledExactlyOnceWith('fresh')
  })

  it('retains unapplied input across detail without submitting on blur or while unmounted', () => {
    vi.useFakeTimers()
    searchSpy.mockClear()
    render(<DraftHarness />)
    const input = screen.getByRole('textbox', { name: '搜索' })
    fireEvent.change(input, { target: { value: ' alpha ' } })
    fireEvent.blur(input)
    expect(searchSpy).not.toHaveBeenCalled()
    fireEvent.click(screen.getByText('切换详情'))
    act(() => vi.advanceTimersByTime(1000))
    expect(searchSpy).not.toHaveBeenCalled()
    fireEvent.click(screen.getByText('切换详情'))
    expect(screen.getByRole('textbox', { name: '搜索' })).toHaveValue(' alpha ')
    act(() => vi.advanceTimersByTime(300))
    expect(searchSpy).toHaveBeenCalledExactlyOnceWith('alpha')
  })

  it('isolates pending drafts by dataset and clears them when the stage closes', () => {
    vi.useFakeTimers()
    searchSpy.mockClear()
    const { rerender } = render(<DraftHarness />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'alpha' } })
    rerender(<DraftHarness dataset="list-2" />)
    expect(screen.getByRole('textbox')).toHaveValue('')
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'beta' } })
    rerender(<DraftHarness />)
    expect(screen.getByRole('textbox')).toHaveValue('alpha')
    rerender(<DraftHarness active={false} />)
    // Drawer children can remain mounted while their closing animation finishes.
    act(() => vi.advanceTimersByTime(1000))
    expect(searchSpy).not.toHaveBeenCalled()
    rerender(<DraftHarness />)
    expect(screen.getByRole('textbox')).toHaveValue('')
    act(() => vi.advanceTimersByTime(1000))
    expect(searchSpy).not.toHaveBeenCalled()
  })

  it('cancels pending input on an external reset', () => {
    vi.useFakeTimers()
    const onSearch = vi.fn()
    const onBlur = vi.fn()
    const { rerender } = render(
      <DebouncedSearchInput aria-label="搜索" value="beta" onSearch={onSearch} onBlur={onBlur} />
    )
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'alpha' } })
    fireEvent.blur(screen.getByRole('textbox'))
    expect(onBlur).toHaveBeenCalledOnce()
    rerender(<DebouncedSearchInput aria-label="搜索" value="" onSearch={onSearch} />)
    act(() => vi.advanceTimersByTime(1000))
    expect(screen.getByRole('textbox')).toHaveValue('')
    expect(onSearch).not.toHaveBeenCalled()
  })

  it('keeps the default debounce behavior on blur', () => {
    vi.useFakeTimers()
    const onSearch = vi.fn()
    render(<DebouncedSearchInput aria-label="搜索" onSearch={onSearch} />)
    const input = screen.getByRole('textbox', { name: '搜索' })
    fireEvent.change(input, { target: { value: 'beta' } })
    fireEvent.blur(input)
    expect(onSearch).not.toHaveBeenCalled()
    act(() => vi.advanceTimersByTime(300))
    expect(onSearch).toHaveBeenCalledExactlyOnceWith('beta')
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('submits only the latest trimmed value after the debounce interval', () => {
    vi.useFakeTimers()
    const onSearch = vi.fn()
    render(<DebouncedSearchInput aria-label="搜索" onSearch={onSearch} />)

    const input = screen.getByRole('textbox', { name: '搜索' })
    fireEvent.change(input, { target: { value: ' a' } })
    fireEvent.change(input, { target: { value: ' alpha ' } })

    act(() => vi.advanceTimersByTime(299))
    expect(onSearch).not.toHaveBeenCalled()

    act(() => vi.advanceTimersByTime(1))
    expect(onSearch).toHaveBeenCalledOnce()
    expect(onSearch).toHaveBeenLastCalledWith('alpha')
  })

  it('submits immediately on Enter and cancels the pending debounce', () => {
    vi.useFakeTimers()
    const onSearch = vi.fn()
    render(<DebouncedSearchInput aria-label="搜索" onSearch={onSearch} />)

    const input = screen.getByRole('textbox', { name: '搜索' })
    fireEvent.change(input, { target: { value: ' beta ' } })
    fireEvent.keyDown(input, { code: 'Enter', key: 'Enter' })

    expect(onSearch).toHaveBeenCalledOnce()
    expect(onSearch).toHaveBeenLastCalledWith('beta')
    act(() => vi.runAllTimers())
    expect(onSearch).toHaveBeenCalledOnce()
  })

  it('clears immediately and follows an external reset', () => {
    vi.useFakeTimers()
    const onSearch = vi.fn()
    const { rerender } = render(
      <DebouncedSearchInput aria-label="搜索" onSearch={onSearch} value="alpha" />
    )

    fireEvent.click(screen.getByLabelText('close-circle'))
    expect(onSearch).toHaveBeenLastCalledWith('')

    rerender(<DebouncedSearchInput aria-label="搜索" onSearch={onSearch} value="server" />)
    expect(screen.getByRole('textbox', { name: '搜索' })).toHaveValue('server')
  })
})
