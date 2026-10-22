import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import TestMailModal from '@/pages/admin/mail/components/TestMailModal'
import ModelProfileModal from '@/pages/admin/models/components/ModelProfileModal'
import TestProfileModal from '@/pages/admin/models/components/TestProfileModal'
import ResetPasswordModal from '@/pages/admin/users/components/ResetPasswordModal'
import UserModal from '@/pages/admin/users/components/UserModal'
import ConcurrencyModal from '@/pages/admin/workers/components/ConcurrencyModal'
import ChangePasswordModal from '@/pages/settings/profile/components/ChangePasswordModal'
import type { AgentRuntime, ModelProfile } from '@/types/admin/models'

const consumers = [
  [
    'user',
    (loading: boolean, onCancel: () => void, onSubmit: () => Promise<void>) => (
      <UserModal visible user={null} {...{ loading, onCancel, onSubmit }} />
    )
  ],
  [
    'reset-password',
    (loading: boolean, onCancel: () => void, onSubmit: () => Promise<void>) => (
      <ResetPasswordModal visible user={null} {...{ loading, onCancel, onSubmit }} />
    )
  ],
  [
    'model',
    (loading: boolean, onCancel: () => void, onSubmit: () => Promise<void>) => (
      <ModelProfileModal visible profile={null} {...{ loading, onCancel, onSubmit }} />
    )
  ],
  [
    'model-test',
    (loading: boolean, onCancel: () => void, onSubmit: () => Promise<void>) => (
      <TestProfileModal
        profile={{ id: 'profile', name: 'test' } as ModelProfile}
        agentRuntimes={[
          { id: 'runtime', name: 'test-runtime', enabled: true, agentType: 'CODEX' } as AgentRuntime
        ]}
        {...{ loading, onCancel, onSubmit }}
      />
    )
  ],
  [
    'mail-test',
    (loading: boolean, onCancel: () => void, onSubmit: () => Promise<void>) => (
      <TestMailModal visible {...{ loading, onCancel, onSubmit }} />
    )
  ],
  [
    'password',
    (loading: boolean, onCancel: () => void, onSubmit: () => Promise<void>) => (
      <ChangePasswordModal visible username="qa" {...{ loading, onCancel, onSubmit }} />
    )
  ],
  [
    'concurrency',
    (loading: boolean, onCancel: () => void, onSubmit: () => Promise<void>) => (
      <ConcurrencyModal visible worker={null} {...{ loading, onCancel, onSubmit }} />
    )
  ]
] as const

describe.each(consumers)('%s submission consumer', (_, content) => {
  it('disables each editable control and every close/submit entry while busy, then unlocks', async () => {
    const cancel = vi.fn(),
      submit = vi.fn(async () => undefined),
      user = userEvent.setup()
    const { container, rerender } = render(content(true, cancel, submit))
    const dialog = screen.getByRole('dialog')
    for (const node of dialog.querySelectorAll('input,textarea,select,button')) {
      if (node.tagName === 'BUTTON' && node.getAttribute('aria-label') === 'Close') continue
      expect(node).toBeDisabled()
    }
    await user.keyboard('{Escape}')
    const wrap = document.querySelector('.ant-modal-wrap')!
    fireEvent.mouseDown(wrap)
    fireEvent.mouseUp(wrap)
    fireEvent.click(wrap)
    const form = container.querySelector('form') ?? dialog.querySelector('form')!
    fireEvent.submit(form)
    expect(cancel).not.toHaveBeenCalled()
    expect(submit).not.toHaveBeenCalled()
    rerender(content(false, cancel, submit))
    expect(screen.getByRole('button', { name: 'Close' })).toBeEnabled()
    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(cancel).toHaveBeenCalledOnce()
  })
})
