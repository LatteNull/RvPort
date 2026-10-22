import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { ProjectWorkflowStatus } from '@/types/project'

import Workflow from './index'

describe('Workflow desktop canvas', () => {
  const workflowStatus: ProjectWorkflowStatus = {
    projectId: 'project-1',
    currentStageId: 'env',
    stages: [
      { id: 'env', status: 'PENDING' },
      { id: 'assets', status: 'DONE' }
    ],
    activeEdgeIds: [],
    updatedAt: ''
  }

  it('keeps the current stage and clicked selection independent when selecting and closing', () => {
    const { rerender } = render(
      <Workflow selectedStageId="assets" workflowStatus={workflowStatus} onStageClick={vi.fn()} />
    )
    const current = screen.getByText('环境管理').closest('[data-status]')
    const selected = screen.getByText('源码管理').closest('[data-status]')

    expect(current).toHaveAttribute('data-current-stage', 'true')
    expect(current).toHaveAttribute('aria-current', 'step')
    expect(current).toHaveAttribute('title', '当前阶段：环境管理')
    expect(current).not.toHaveAttribute('data-selected')
    expect(screen.getByText('当前阶段').closest('[data-status]')).toBe(current)
    expect(selected).toHaveAttribute('data-selected', 'true')
    expect(selected).not.toHaveAttribute('data-current-stage')

    rerender(
      <Workflow selectedStageId="env" workflowStatus={workflowStatus} onStageClick={vi.fn()} />
    )
    expect(current).toHaveAttribute('data-current-stage', 'true')
    expect(current).toHaveAttribute('data-selected', 'true')
    expect(selected).not.toHaveAttribute('data-selected')

    rerender(<Workflow workflowStatus={workflowStatus} onStageClick={vi.fn()} />)
    expect(current).toHaveAttribute('data-current-stage', 'true')
    expect(current).not.toHaveAttribute('data-selected')
  })

  it.each(['PENDING', 'RUNNING', 'BLOCKED'] as const)(
    'preserves %s business status on the current and selected stage',
    (status) => {
      render(
        <Workflow
          selectedStageId="env"
          workflowStatus={{ ...workflowStatus, stages: [{ id: 'env', status }] }}
          onStageClick={vi.fn()}
        />
      )
      const node = screen.getByText('环境管理').closest('[data-status]')

      expect(node).toHaveAttribute('data-current-stage', 'true')
      expect(node).toHaveAttribute('data-selected', 'true')
      expect(node).toHaveAttribute('data-status', status.toLowerCase())
      expect(screen.getByText('当前阶段').closest('[data-status]')).toBe(node)
    }
  )

  it('does not switch to a mobile-only navigation when the viewport is narrow', () => {
    vi.spyOn(window, 'matchMedia').mockImplementation(
      (query) =>
        ({
          addEventListener: vi.fn(),
          addListener: vi.fn(),
          dispatchEvent: vi.fn(),
          matches: query.includes('max-width'),
          media: query,
          onchange: null,
          removeEventListener: vi.fn(),
          removeListener: vi.fn()
        }) as unknown as MediaQueryList
    )

    render(<Workflow onStageClick={vi.fn()} />)

    expect(screen.queryByRole('region', { name: '项目阶段导航' })).not.toBeInTheDocument()
    expect(screen.getByText('项目基础配置')).toBeInTheDocument()
  })
})
