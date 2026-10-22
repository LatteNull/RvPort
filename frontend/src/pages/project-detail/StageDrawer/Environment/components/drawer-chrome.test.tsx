import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { EnvironmentDrawerTitle } from './drawer-chrome'

describe('EnvironmentDrawerTitle', () => {
  it('exposes a scoped refresh action for the environment list', async () => {
    const onRefresh = vi.fn(async () => {})
    const user = userEvent.setup()

    render(
      <EnvironmentDrawerTitle
        stage={null}
        view={{ type: 'list' }}
        onBack={vi.fn()}
        onRefresh={onRefresh}
      />
    )

    const refreshButton = screen.getByRole('button', { name: '刷新环境列表' })
    expect(refreshButton).not.toHaveTextContent('刷新')

    await user.click(refreshButton)

    expect(onRefresh).toHaveBeenCalledTimes(1)
  })

  it('does not offer refresh while editing unsaved configuration', () => {
    render(
      <EnvironmentDrawerTitle
        stage={null}
        view={{ environment: {} as never, type: 'edit' }}
        onBack={vi.fn()}
        onRefresh={vi.fn()}
      />
    )

    expect(screen.queryByRole('button', { name: /刷新/ })).not.toBeInTheDocument()
  })

  it('blocks Workflow internal back during submission and restores it afterward', async () => {
    const onBack = vi.fn()
    const user = userEvent.setup()
    const props = {
      showBack: true,
      view: { type: 'create' as const },
      onBack,
      onRefresh: vi.fn(async () => {})
    }
    const { rerender } = render(<EnvironmentDrawerTitle {...props} busy />)
    expect(screen.getByRole('button', { name: '返回' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: '返回' }))
    expect(onBack).not.toHaveBeenCalled()
    rerender(<EnvironmentDrawerTitle {...props} />)
    await user.click(screen.getByRole('button', { name: '返回' }))
    expect(onBack).toHaveBeenCalledOnce()
  })

  it('uses the drawer close action for history and an internal back action only for logs', async () => {
    const onBack = vi.fn()
    const user = userEvent.setup()
    const { rerender } = render(
      <EnvironmentDrawerTitle
        stage={null}
        view={{ environment: {} as never, type: 'history' }}
        onBack={onBack}
        onRefresh={vi.fn(async () => {})}
      />
    )

    expect(screen.queryByRole('button', { name: '返回' })).not.toBeInTheDocument()

    rerender(
      <EnvironmentDrawerTitle
        stage={null}
        view={{ environment: {} as never, executionId: 'execution-1', type: 'log' }}
        onBack={onBack}
        onRefresh={vi.fn(async () => {})}
      />
    )

    await user.click(screen.getByRole('button', { name: '返回' }))
    expect(onBack).toHaveBeenCalledOnce()
  })
})
