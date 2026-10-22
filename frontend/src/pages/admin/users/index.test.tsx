import { Fragment, type ReactNode } from 'react'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '@/test/test-utils'

const { sendAdminUserInvitation } = vi.hoisted(() => ({
  sendAdminUserInvitation: vi.fn()
}))

vi.mock('@/api/admin/users', () => ({
  createAdminUser: vi.fn(),
  getAdminUsers: vi.fn(),
  resetAdminUserPassword: vi.fn(),
  sendAdminUserInvitation,
  updateAdminUser: vi.fn()
}))

vi.mock('@/components/BaseTable', () => ({
  default: ({
    columns
  }: {
    columns: Array<{ key?: string; render?: (value: unknown, record: unknown) => ReactNode }>
  }) => {
    const actions = columns.find((column) => column.key === 'actions')
    return <Fragment>{actions?.render?.(undefined, user)}</Fragment>
  }
}))

import AdminUsersPage from '.'

const user = {
  id: 'user-1',
  username: 'developer',
  displayName: '开发人员',
  email: 'developer@example.com',
  isSuperAdmin: false,
  mustChangePassword: false,
  status: 'ACTIVE',
  lastLoginAt: null,
  createdAt: '2026-08-01T09:00:00+08:00',
  updatedAt: null
}

describe('admin user page', () => {
  it('requires confirmation before resending an invitation', async () => {
    sendAdminUserInvitation.mockResolvedValue(user)
    const userEventInstance = userEvent.setup()

    renderWithQueryClient(<AdminUsersPage />)

    await userEventInstance.click(screen.getByRole('button', { name: '重发邀请' }))

    expect(sendAdminUserInvitation).not.toHaveBeenCalled()
    await userEventInstance.click(screen.getByRole('button', { name: '确认重发' }))

    await waitFor(() => {
      expect(sendAdminUserInvitation.mock.calls[0]?.[0]).toBe('user-1')
    })
  })
})
