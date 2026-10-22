import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import StageStateNotice, { type StageStateVariant } from '.'

const variants: Array<{ icon: string; variant: StageStateVariant }> = [
  { icon: 'lock', variant: 'prerequisite' },
  { icon: 'check-circle', variant: 'ready' },
  { icon: 'file-add', variant: 'empty' },
  { icon: 'loading-3-quarters', variant: 'processing' },
  { icon: 'exclamation-circle', variant: 'partial' },
  { icon: 'close-circle', variant: 'execution-error' },
  { icon: 'disconnect', variant: 'request-error' }
]

describe('StageStateNotice', () => {
  it.each(variants)('renders the $variant state with a meaningful icon', ({ icon, variant }) => {
    const { container } = render(
      <StageStateNotice description="状态说明" title="状态标题" variant={variant} />
    )

    expect(screen.getByRole('status')).toHaveAttribute('data-variant', variant)
    expect(container.querySelector(`[data-icon="${icon}"]`)).toBeInTheDocument()
    expect(screen.getByText('状态标题')).toBeInTheDocument()
    expect(screen.getByText('状态说明')).toBeInTheDocument()
  })

  it('keeps the state action explicit', async () => {
    const onReload = vi.fn()
    const user = userEvent.setup()
    render(
      <StageStateNotice
        description="无法读取最新记录"
        primaryAction={{ label: '重新加载', onClick: onReload }}
        title="数据加载失败"
        variant="request-error"
      />
    )

    await user.click(screen.getByRole('button', { name: '重新加载' }))
    expect(onReload).toHaveBeenCalledOnce()
  })

  it('supports confirmation for a state action', async () => {
    const onConfirm = vi.fn()
    const user = userEvent.setup()
    render(
      <StageStateNotice
        description="当前条件已满足"
        primaryAction={{
          confirmation: {
            cancelText: '取消',
            description: '将创建不可变快照。',
            okText: '确认创建',
            title: '确认创建归档？'
          },
          label: '创建归档',
          onClick: onConfirm
        }}
        title="可以创建归档"
        variant="ready"
      />
    )

    await user.click(screen.getByRole('button', { name: '创建归档' }))
    expect(onConfirm).not.toHaveBeenCalled()
    await user.click(await screen.findByRole('button', { name: '确认创建' }))
    expect(onConfirm).toHaveBeenCalledOnce()
  })

  it('renders the core action first and history as the final link action', () => {
    render(
      <StageStateNotice
        description="状态说明"
        primaryAction={{ label: '核心操作', onClick: vi.fn() }}
        secondaryActions={[
          { label: '重新执行', onClick: vi.fn() },
          { label: '查看历史记录', onClick: vi.fn(), type: 'link' }
        ]}
        title="状态标题"
        variant="execution-error"
      />
    )

    const buttons = screen.getAllByRole('button')
    expect(buttons.map((button) => button.textContent)).toEqual([
      '核心操作',
      '重新执行',
      '查看历史记录'
    ])
    expect(screen.getByRole('button', { name: '核心操作' })).toHaveClass('ant-btn-primary')
    expect(screen.getByRole('button', { name: '重新执行' })).toHaveClass('ant-btn-default')
    expect(screen.getByRole('button', { name: '查看历史记录' })).toHaveClass('ant-btn-link')
  })

  it('keeps each prerequisite action next to its own status', async () => {
    const onManageSource = vi.fn()
    render(
      <StageStateNotice
        description="完成以下条件后继续"
        prerequisites={[
          {
            action: { label: '前往源码管理', onClick: onManageSource },
            key: 'source',
            label: '当前源码',
            ready: false,
            value: '未激活'
          },
          { key: 'environment', label: '目标环境', ready: true, value: '已准备' }
        ]}
        title="暂不能执行"
        variant="prerequisite"
      />
    )

    expect(screen.getByText('当前源码')).toBeInTheDocument()
    expect(screen.getByText('未激活')).toBeInTheDocument()
    expect(screen.getByText('目标环境')).toBeInTheDocument()
    expect(screen.getByText('已准备')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /目标环境/ })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '前往源码管理' }))
    expect(onManageSource).toHaveBeenCalledOnce()
  })

  it('announces a processing state', () => {
    render(
      <StageStateNotice description="任务正在后台执行" title="正在执行" variant="processing" />
    )

    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite')
  })
})
