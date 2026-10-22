import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '@/test/test-utils'

vi.mock('@/components/BaseDrawer', () => ({
  default: ({
    children,
    footer,
    title
  }: {
    children: React.ReactNode
    footer?: React.ReactNode
    title: React.ReactNode
  }) => (
    <div>
      {title}
      {children}
      {footer}
    </div>
  )
}))

import ManualRepair from '.'

const stage = {
  id: 'manual',
  order: 8,
  status: 'pending' as const,
  subtitle: '',
  title: '人工修复'
}

function renderDrawer(onStageChange = vi.fn()) {
  return {
    onStageChange,
    ...renderWithQueryClient(
      <ManualRepair
        projectId="project-1"
        stage={stage}
        visible
        onClose={vi.fn()}
        onStageChange={onStageChange}
      />
    )
  }
}

describe('Manual repair drawer', () => {
  it('guides dependency and source repairs to their corresponding stages', async () => {
    const { onStageChange } = renderDrawer()
    expect(screen.getByText('根据问题类型完成修复')).toBeInTheDocument()
    expect(screen.getByText('修复依赖问题')).toBeInTheDocument()
    expect(screen.getByText('修复源码问题')).toBeInTheDocument()

    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: '查看依赖分析' }))
    expect(onStageChange).toHaveBeenCalledWith('rv-dependency-analysis')

    await user.click(screen.getByRole('button', { name: '前往源码管理' }))
    expect(onStageChange).toHaveBeenCalledWith('assets')

    await user.click(screen.getByRole('button', { name: '前往构建验证' }))
    expect(onStageChange).toHaveBeenCalledWith('build')
  })
})
