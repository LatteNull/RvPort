import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import StageViewLoading from '.'

describe('StageViewLoading', () => {
  it('renders a structural skeleton for a known view layout', () => {
    render(<StageViewLoading description="正在加载详情" variant="detail" />)

    const loadingView = screen.getByRole('status', { name: '正在加载详情' })

    expect(loadingView).toHaveAttribute('aria-busy', 'true')
    expect(loadingView).toHaveAttribute('data-variant', 'detail')
    expect(loadingView.querySelector('section')).toBeInTheDocument()
    expect(loadingView.querySelector('aside')).toBeInTheDocument()
  })

  it('renders a centered spinner for data with no predictable structure', () => {
    render(<StageViewLoading description="正在加载扫描信息" />)

    const loadingView = screen.getByRole('status', { name: '正在加载扫描信息' })

    expect(loadingView).toHaveAttribute('aria-busy', 'true')
    expect(loadingView).not.toHaveAttribute('data-variant')
    expect(screen.getByText('正在加载扫描信息')).toBeInTheDocument()
  })
})
