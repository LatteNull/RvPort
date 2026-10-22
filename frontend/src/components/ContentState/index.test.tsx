import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import ContentState from '.'

describe('ContentState', () => {
  it('announces loading without exposing retry actions', () => {
    render(<ContentState kind="loading" description="正在加载结果" />)
    expect(screen.getByRole('status', { name: '正在加载结果' })).toHaveAttribute(
      'aria-busy',
      'true'
    )
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('keeps the error action wired to the caller', async () => {
    const retry = vi.fn()
    render(
      <ContentState kind="error" description="结果加载失败" details="请重新加载">
        <button onClick={retry}>重试</button>
      </ContentState>
    )
    expect(screen.getByRole('alert', { name: '结果加载失败' })).not.toHaveAttribute('aria-busy')
    await userEvent.click(screen.getByRole('button', { name: '重试' }))
    expect(retry).toHaveBeenCalledOnce()
  })

  it('distinguishes an empty filtered result from a request failure', () => {
    render(<ContentState compact kind="filtered" description="没有匹配的结果" />)
    expect(screen.getByRole('status', { name: '没有匹配的结果' })).toHaveAttribute(
      'data-state',
      'filtered'
    )
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
