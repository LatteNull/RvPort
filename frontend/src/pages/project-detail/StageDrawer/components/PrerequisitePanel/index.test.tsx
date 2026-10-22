import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import PrerequisitePanel from '.'

describe('PrerequisitePanel', () => {
  it('renders every condition and keeps recovery actions with their own item', async () => {
    const openSource = vi.fn()
    const openEnvironment = vi.fn()
    render(
      <PrerequisitePanel
        description="请完成下方未满足的前置条件。"
        items={[
          {
            actionLabel: '前往源码管理',
            key: 'source',
            label: '当前源码',
            onAction: openSource,
            value: '尚未配置'
          },
          {
            actionLabel: '前往环境管理',
            key: 'environment',
            label: '当前环境',
            onAction: openEnvironment,
            value: '尚未配置完整'
          }
        ]}
        ready={false}
        title="暂不能开始构建"
      />
    )

    expect(screen.getByText('当前源码')).toBeInTheDocument()
    expect(screen.getByText('当前环境')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '前往源码管理' }))
    await userEvent.click(screen.getByRole('button', { name: '前往环境管理' }))
    expect(openSource).toHaveBeenCalledOnce()
    expect(openEnvironment).toHaveBeenCalledOnce()
  })

  it('renders a repository value as an external link', () => {
    render(
      <PrerequisitePanel
        items={[
          {
            href: 'https://github.com/ISCAS/RvPort.git',
            key: 'source',
            label: '当前源码',
            value: 'RvPort'
          }
        ]}
        ready
        title="可以开始构建"
      />
    )

    expect(screen.getByRole('link', { name: 'RvPort' })).toHaveAttribute(
      'href',
      'https://github.com/ISCAS/RvPort.git'
    )
  })
})
