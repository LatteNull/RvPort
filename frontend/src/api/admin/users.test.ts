import { describe, expect, it, vi } from 'vitest'

const { request } = vi.hoisted(() => ({
  request: {
    get: vi.fn(),
    patch: vi.fn(),
    post: vi.fn(),
    put: vi.fn()
  }
}))

vi.mock('../request', () => ({
  default: request,
  LONG_RUNNING_REQUEST_TIMEOUT_MS: 3_600_000
}))

import {
  createAdminUser,
  getAdminUsers,
  resetAdminUserPassword,
  sendAdminUserInvitation,
  updateAdminUser
} from '@/api/admin/users'

describe('users API contract', () => {
  it('uses documented user-management endpoints and request payloads', () => {
    getAdminUsers({ keyword: 'developer', page: 2, pageSize: 10, status: 'ACTIVE' })
    createAdminUser({
      displayName: '开发人员',
      email: 'developer@example.com',
      username: 'developer'
    })
    updateAdminUser('user-1', { status: 'DISABLED' })
    resetAdminUserPassword('user-1', { mustChangePassword: true, newPassword: 'NewPassword1' })
    sendAdminUserInvitation('user-1')

    expect(request.get).toHaveBeenCalledWith('/admin/users', {
      params: { keyword: 'developer', page: 2, pageSize: 10, status: 'ACTIVE' }
    })
    expect(request.post).toHaveBeenNthCalledWith(1, '/admin/users', {
      displayName: '开发人员',
      email: 'developer@example.com',
      username: 'developer'
    })
    expect(request.patch).toHaveBeenNthCalledWith(1, '/admin/users/user-1', { status: 'DISABLED' })
    expect(request.post).toHaveBeenNthCalledWith(2, '/admin/users/user-1/reset-password', {
      mustChangePassword: true,
      newPassword: 'NewPassword1'
    })
    expect(request.post).toHaveBeenNthCalledWith(3, '/admin/users/user-1/send-invitation')
  })
})
