import { MemoryRouter, useLocation } from 'react-router'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '@/test/test-utils'

const { confirmPasswordReset } = vi.hoisted(() => ({ confirmPasswordReset: vi.fn() }))

vi.mock('@/api/auth', () => ({ confirmPasswordReset }))
vi.mock('@/utils/feedback', () => ({ feedback: { success: vi.fn() } }))

import ResetPasswordPage from '.'

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{`${location.pathname}${location.search}`}</output>
}

describe('reset password page', () => {
  it('submits the token and new password', async () => {
    confirmPasswordReset.mockResolvedValue({})
    const user = userEvent.setup()

    renderWithQueryClient(
      <MemoryRouter initialEntries={['/reset-password?token=reset-token']}>
        <ResetPasswordPage />
        <LocationProbe />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/reset-password')
      expect(screen.getByTestId('location')).not.toHaveTextContent('token=')
    })

    await user.type(screen.getByLabelText('新密码'), 'NewPassword1')
    await user.type(screen.getByLabelText('确认新密码'), 'NewPassword1')
    await user.click(screen.getByRole('button', { name: '重置密码' }))

    await waitFor(() => {
      expect(confirmPasswordReset).toHaveBeenCalled()
    })
    expect(confirmPasswordReset.mock.calls[0]?.[0]).toEqual({
      token: 'reset-token',
      newPassword: 'NewPassword1'
    })
  })

  it('does not render the password form without a token', () => {
    renderWithQueryClient(
      <MemoryRouter>
        <ResetPasswordPage />
      </MemoryRouter>
    )

    expect(screen.getByText('重置链接无效或已过期，请重新申请。')).toBeInTheDocument()
    expect(screen.queryByLabelText('新密码')).not.toBeInTheDocument()
  })
})
