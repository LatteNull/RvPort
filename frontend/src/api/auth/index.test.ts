import { describe, expect, it, vi } from 'vitest'

const { patch, post } = vi.hoisted(() => ({ patch: vi.fn(), post: vi.fn() }))

vi.mock('@/api/request', () => ({
  default: { patch, post }
}))

import { confirmPasswordReset, requestPasswordReset, updateProfile } from '.'

describe('auth API', () => {
  it('sends only the display name to the profile endpoint', () => {
    updateProfile({ displayName: '迁移管理员' })

    expect(patch).toHaveBeenCalledWith('/auth/profile', { displayName: '迁移管理员' })
  })

  it('sends password reset requests using the documented endpoints', () => {
    requestPasswordReset({ identifier: 'admin@example.com' })
    confirmPasswordReset({ token: 'reset-token', newPassword: 'NewPassword1' })

    expect(post).toHaveBeenNthCalledWith(1, '/auth/password-resets/request', {
      identifier: 'admin@example.com'
    })
    expect(post).toHaveBeenNthCalledWith(2, '/auth/password-resets/confirm', {
      token: 'reset-token',
      newPassword: 'NewPassword1'
    })
  })
})
