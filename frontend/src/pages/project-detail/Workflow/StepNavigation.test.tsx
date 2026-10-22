import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import StepNavigation from './StepNavigation'
import { workflowGroups, workflowStages } from './topology'

describe('Step 阶段导航', () => {
  it('保留旧版分组、状态与选中反馈，全部阶段均可通过键盘进入', async () => {
    const onStageClick = vi.fn()
    const user = userEvent.setup()
    render(
      <StepNavigation
        selectedStageId="env"
        onStageClick={onStageClick}
        workflowStatus={{
          projectId: 'p1',
          currentStageId: 'report',
          activeEdgeIds: [],
          updatedAt: '',
          stages: [
            { id: 'env', status: 'BLOCKED' },
            { id: 'report', status: 'RUNNING' }
          ]
        }}
      />
    )

    const navigation = screen.getByRole('navigation', { name: '阶段导航' })
    expect(within(navigation).getAllByRole('button')).toHaveLength(workflowStages.length)
    expect(within(navigation).getByRole('region', { name: '项目' })).toBeInTheDocument()
    for (const group of workflowGroups) {
      expect(within(navigation).getByRole('region', { name: group.title })).toBeInTheDocument()
    }

    const env = within(navigation).getByRole('button', { name: /^环境管理/ })
    expect(env).toHaveAttribute('aria-current', 'step')
    expect(env).toHaveTextContent('阻塞')
    const report = within(navigation).getByRole('button', { name: /^评估报告/ })
    expect(report).not.toHaveAttribute('aria-current')
    expect(report).toHaveTextContent('进行中')
    env.focus()
    await user.keyboard('{Enter}')
    expect(onStageClick).toHaveBeenCalledWith('env')
  })
})
