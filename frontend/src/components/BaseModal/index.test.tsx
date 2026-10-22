import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import BaseModal from '.'

describe('BaseModal', () => {
  it('mounts form content while closed so form instances can connect', () => {
    render(
      <BaseModal forceRender visible={false}>
        <form aria-label="预挂载表单" />
      </BaseModal>
    )

    expect(screen.getByRole('form', { hidden: true, name: '预挂载表单' })).toBeInTheDocument()
  })
})

describe('busy close boundaries', () => {
  it('blocks close, keyboard, mask and default buttons while busy and restores them afterward', async () => {
    const { fireEvent } = await import('@testing-library/react')
    const { default: userEvent } = await import('@testing-library/user-event')
    const { vi } = await import('vitest')
    const onCancel = vi.fn(),
      onOk = vi.fn()
    const user = userEvent.setup()
    const { rerender } = render(
      <BaseModal busy visible title="提交事务" onCancel={onCancel} onOk={onOk}>
        <input aria-label="普通内容" />
      </BaseModal>
    )
    expect(screen.queryByRole('button', { name: 'Close' })).not.toBeInTheDocument()
    await user.keyboard('{Escape}')
    const wrap = document.querySelector('.ant-modal-wrap')!
    fireEvent.mouseDown(wrap)
    fireEvent.mouseUp(wrap)
    fireEvent.click(wrap)
    expect(onCancel).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled()
    expect(screen.getByRole('button', { name: /O\s*K/ })).toBeDisabled()
    rerender(
      <BaseModal visible title="提交事务" onCancel={onCancel} onOk={onOk}>
        <input />
      </BaseModal>
    )
    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(onCancel).toHaveBeenCalledOnce()
    await user.click(screen.getByRole('button', { name: /O\s*K/ }))
    expect(onOk).toHaveBeenCalledOnce()
  })
})
