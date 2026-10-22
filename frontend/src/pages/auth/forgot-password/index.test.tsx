import { MemoryRouter } from 'react-router'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '@/test/test-utils'

const { requestPasswordReset } = vi.hoisted(() => ({ requestPasswordReset: vi.fn() }))

vi.mock('@/api/auth', () => ({ requestPasswordReset }))
vi.mock('@/utils/feedback', () => ({ feedback: { success: vi.fn() } }))

import ForgotPasswordPage from '.'

describe('forgot password page', () => {
  it('submits an identifier and shows the neutral success state', async () => {
    requestPasswordReset.mockResolvedValue({ accepted: true })
    const user = userEvent.setup()

    renderWithQueryClient(
      <MemoryRouter>
        <ForgotPasswordPage />
      </MemoryRouter>
    )

    await user.type(screen.getByLabelText('账号或邮箱'), 'admin@example.com')
    await user.click(screen.getByRole('button', { name: '发送重置链接' }))

    await waitFor(() => {
      expect(requestPasswordReset).toHaveBeenCalled()
    })
    expect(requestPasswordReset.mock.calls[0]?.[0]).toEqual({ identifier: 'admin@example.com' })
    expect(screen.getByText('请查看邮箱中的密码重置链接。')).toBeInTheDocument()
  })
})
