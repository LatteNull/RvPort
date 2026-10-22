import { act, fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { advanceAuthSession } from '@/store/authSession'

vi.mock('@/components/BaseDrawer', () => ({
  default: ({
    children,
    title,
    visible
  }: {
    children: React.ReactNode
    title?: unknown
    visible: boolean
  }) =>
    visible ? (
      <section aria-label="阶段抽屉">
        <span>{typeof title === 'object' ? '阻断阶段' : String(title ?? '')}</span>
        {children}
      </section>
    ) : null
}))

vi.mock('./Assets', () => ({
  default: ({ stage }: { stage?: { status: string } }) => (
    <div>
      <span>{`源码管理内容:${stage?.status ?? ''}`}</span>
      <input aria-label="Drawer 内部状态" />
    </div>
  )
}))

import StageDrawer from './index'

describe('StageDrawer', () => {
  it('keeps the domain drawer mounted when its workflow status is blocked', async () => {
    const onClose = vi.fn()
    const { rerender } = render(
      <StageDrawer
        projectId="project-1"
        visible
        stage={{
          id: 'assets',
          order: 3,
          status: 'done',
          subtitle: 'Git / 源码压缩包',
          title: '源码管理'
        }}
        onClose={onClose}
      />
    )

    fireEvent.change(await screen.findByRole('textbox', { name: 'Drawer 内部状态' }), {
      target: { value: '保留输入' }
    })
    rerender(
      <StageDrawer
        projectId="project-1"
        visible
        stage={{
          id: 'assets',
          order: 3,
          status: 'blocked',
          subtitle: 'Git / 源码压缩包',
          title: '源码管理'
        }}
        onClose={onClose}
      />
    )

    expect(await screen.findByText('源码管理内容:blocked')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Drawer 内部状态' })).toHaveValue('保留输入')
    expect(screen.queryByText('当前模块仅可查看')).not.toBeInTheDocument()
  })

  it('retains the active drawer component while it closes', async () => {
    const onClose = vi.fn()
    const { rerender } = render(
      <StageDrawer
        projectId="project-1"
        visible
        stage={{
          id: 'assets',
          order: 3,
          status: 'done',
          subtitle: 'Git / 源码压缩包',
          title: '源码管理'
        }}
        onClose={onClose}
      />
    )

    expect(await screen.findByText('源码管理内容:done')).toBeInTheDocument()

    rerender(
      <StageDrawer projectId="project-1" visible={false} stage={undefined} onClose={onClose} />
    )

    expect(screen.getByText('源码管理内容:done')).toBeInTheDocument()
  })
  it('preserves a draft across presentation changes but resets it across projects and identities', async () => {
    const stage = { id: 'assets', order: 3, status: 'done' as const, subtitle: '', title: '源码' }
    const props = { projectId: 'A', visible: true, stage, onClose: vi.fn() }
    const { rerender } = render(<StageDrawer {...props} />)
    fireEvent.change(await screen.findByRole('textbox'), { target: { value: 'draft-A' } })
    rerender(<StageDrawer {...props} presentation="panel" />)
    expect(screen.getByRole('textbox')).toHaveValue('draft-A')
    rerender(<StageDrawer {...props} projectId="B" presentation="panel" />)
    expect(screen.getByRole('textbox')).toHaveValue('')
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'draft-B' } })
    act(() => advanceAuthSession())
    expect(screen.getByRole('textbox')).toHaveValue('')
  })
})
