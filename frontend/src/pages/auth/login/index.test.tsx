import { MemoryRouter, useLocation } from 'react-router'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { resetAuthStoreForTests, useAuthStore } from '@/store/authStore'
import type { User } from '@/types'

const { login } = vi.hoisted(() => ({ login: vi.fn() }))

vi.mock('@/api/auth', () => ({ login }))
vi.mock('@/utils/feedback', () => ({ feedback: { success: vi.fn() } }))

import LoginPage from '.'

const user: User = {
  id: 'user-1',
  username: 'admin',
  displayName: 'Admin',
  email: 'admin@example.com',
  isSuperAdmin: true,
  mustChangePassword: false,
  status: 'ACTIVE',
  lastLoginAt: null,
  createdAt: '2026-07-01T09:00:00+08:00',
  updatedAt: null
}

describe('login page', () => {
  beforeEach(() => {
    window.localStorage.clear()
    resetAuthStoreForTests()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    window.localStorage.clear()
    resetAuthStoreForTests()
  })

  it.each(['rvport.remembered-username'])(
    'refills and clears the remembered username from %s without storing a password',
    async (key) => {
      window.localStorage.setItem(key, 'saved-account')
      const userEventInstance = userEvent.setup()

      render(
        <MemoryRouter>
          <LoginPage />
        </MemoryRouter>
      )

      expect(screen.getByRole('img', { name: 'RvPort' })).toBeInTheDocument()
      expect(screen.queryByText('ISCAS 管理平台')).not.toBeInTheDocument()
      expect(screen.getByLabelText('账号')).toHaveValue('saved-account')
      expect(screen.getByRole('checkbox', { name: '记住账号' })).toBeChecked()

      await userEventInstance.click(screen.getByRole('checkbox', { name: '记住账号' }))

      expect(window.localStorage.getItem('rvport.remembered-username')).toBeNull()
      expect(window.localStorage.getItem('password')).toBeNull()
    }
  )

  it('shows only the required error for an empty password and rejects whitespace separately', async () => {
    const interaction = userEvent.setup()
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    )
    expect(screen.getByRole('main')).toBeInTheDocument()
    await interaction.click(screen.getByRole('button', { name: /登\s*录/ }))
    expect(await screen.findByText('请输入密码')).toBeInTheDocument()
    expect(screen.queryByText('密码不能只包含空白字符')).not.toBeInTheDocument()
    await interaction.type(screen.getByLabelText('密码'), '   ')
    await interaction.click(screen.getByRole('button', { name: /登\s*录/ }))
    expect(await screen.findByText('密码不能只包含空白字符')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText('请输入密码')).not.toBeInTheDocument())
  })

  it('stores only the username after a remembered successful login', async () => {
    login.mockResolvedValue({ user })
    const userEventInstance = userEvent.setup()

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    )

    await userEventInstance.type(screen.getByLabelText('账号'), 'admin')
    await userEventInstance.type(screen.getByLabelText('密码'), '123456')
    await userEventInstance.click(screen.getByRole('checkbox', { name: '记住账号' }))
    await userEventInstance.click(screen.getByRole('button', { name: /登\s*录/ }))

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith({ username: 'admin', password: '123456' })
    })
    expect(window.localStorage.getItem('rvport.remembered-username')).toBe('admin')
    expect(window.localStorage.getItem('password')).toBeNull()
  })

  it('opens the password reset request page', async () => {
    const userEventInstance = userEvent.setup()
    function LocationDisplay() {
      return <output data-testid="location">{useLocation().pathname}</output>
    }

    render(
      <MemoryRouter>
        <LoginPage />
        <LocationDisplay />
      </MemoryRouter>
    )

    await userEventInstance.click(screen.getByRole('button', { name: '忘记密码' }))

    expect(screen.getByTestId('location')).toHaveTextContent('/forgot-password')
  })

  it.each(['getItem', 'setItem', 'removeItem'] as const)(
    'still completes login when storage %s is unavailable',
    async (operation) => {
      vi.spyOn(Storage.prototype, operation).mockImplementation(() => {
        throw new DOMException('Storage unavailable', 'SecurityError')
      })
      login.mockResolvedValue({ user })
      const events = userEvent.setup()
      function LocationDisplay() {
        return <output data-testid="location">{useLocation().pathname}</output>
      }
      render(
        <MemoryRouter initialEntries={['/login']}>
          <LoginPage />
          <LocationDisplay />
        </MemoryRouter>
      )
      await events.type(screen.getByLabelText('账号'), 'admin')
      await events.type(screen.getByLabelText('密码'), '123456')
      if (operation === 'setItem')
        await events.click(screen.getByRole('checkbox', { name: '记住账号' }))
      await events.click(screen.getByRole('button', { name: /登\s*录/ }))
      await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/home'))
      expect(useAuthStore.getState().user?.id).toBe(user.id)
    }
  )
})
