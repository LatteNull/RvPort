import { MemoryRouter, useLocation } from 'react-router'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '@/test/test-utils'

const { acceptInvitation } = vi.hoisted(() => ({ acceptInvitation: vi.fn() }))

vi.mock('@/api/auth', () => ({ acceptInvitation }))
vi.mock('@/utils/feedback', () => ({ feedback: { success: vi.fn() } }))

import AcceptInvitationPage from '.'

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{`${location.pathname}${location.search}`}</output>
}

describe('accept invitation page', () => {
  it('submits the invitation token and password', async () => {
    acceptInvitation.mockResolvedValue({})
    const user = userEvent.setup()

    renderWithQueryClient(
      <MemoryRouter initialEntries={['/accept-invitation?token=invitation-token']}>
        <AcceptInvitationPage />
        <LocationProbe />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/accept-invitation')
      expect(screen.getByTestId('location')).not.toHaveTextContent('token=')
    })

    await user.type(screen.getByLabelText('新密码'), 'NewPassword1')
    await user.type(screen.getByLabelText('确认新密码'), 'NewPassword1')
    await user.click(screen.getByRole('button', { name: '完成注册' }))

    await waitFor(() => {
      expect(acceptInvitation).toHaveBeenCalled()
    })
    expect(acceptInvitation.mock.calls[0]?.[0]).toEqual({
      token: 'invitation-token',
      newPassword: 'NewPassword1'
    })
  })

  it('does not render the password form without a token', () => {
    renderWithQueryClient(
      <MemoryRouter>
        <AcceptInvitationPage />
      </MemoryRouter>
    )

    expect(screen.getByText('邀请链接无效或已过期，请联系管理员重新发送邀请。')).toBeInTheDocument()
    expect(screen.queryByLabelText('新密码')).not.toBeInTheDocument()
  })
})
