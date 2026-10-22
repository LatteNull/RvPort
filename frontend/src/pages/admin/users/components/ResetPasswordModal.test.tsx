import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '@/test/test-utils'
import type { User } from '@/types'

import ResetPasswordModal from './ResetPasswordModal'

const user: User = {
  id: 'user-1',
  username: 'developer',
  displayName: 'Developer',
  email: 'developer@example.com',
  isSuperAdmin: false,
  mustChangePassword: false,
  status: 'ACTIVE',
  lastLoginAt: null,
  createdAt: '2026-07-01T09:00:00+08:00',
  updatedAt: null
}

describe('reset password modal', () => {
  it('clears a password draft when the target user changes', async () => {
    const props = { loading: false, visible: true, onCancel: vi.fn(), onSubmit: vi.fn() }
    const { rerender } = renderWithQueryClient(<ResetPasswordModal {...props} user={user} />)
    await userEvent.type(screen.getByLabelText('新密码'), 'NewPassword1')
    rerender(<ResetPasswordModal {...props} user={{ ...user, id: 'user-2', username: 'other' }} />)
    expect(screen.getByLabelText('新密码')).toHaveValue('')
  })

  it('submits a temporary password after confirmation', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    const userEventInstance = userEvent.setup()

    renderWithQueryClient(
      <ResetPasswordModal
        loading={false}
        user={user}
        visible
        onCancel={vi.fn()}
        onSubmit={onSubmit}
      />
    )

    await userEventInstance.type(screen.getByLabelText('新密码'), 'NewPassword1')
    await userEventInstance.type(screen.getByLabelText('确认新密码'), 'NewPassword1')
    await userEventInstance.click(screen.getByRole('button', { name: '重置密码' }))
    await userEventInstance.click(screen.getByRole('button', { name: '确认重置' }))

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        newPassword: 'NewPassword1'
      })
    })
  })
})
