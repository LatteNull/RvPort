import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { advanceAuthSession } from '@/store/authSession'
import { AuthRequiredError, resetAuthStoreForTests, useAuthStore } from '@/store/authStore'

import {
  requireAdmin,
  requireAuth,
  requireFullAccess,
  requireGuest,
  requirePasswordChange
} from './guards'

async function expectRedirect(action: () => Promise<unknown>, location: string) {
  try {
    await action()
    throw new Error('Expected route loader to redirect')
  } catch (error) {
    expect(error).toMatchObject({ status: 302 })
    expect((error as Response).headers.get('Location')).toBe(location)
  }
}

describe('route guards', () => {
  beforeEach(() => {
    resetAuthStoreForTests()
  })

  afterEach(() => {
    resetAuthStoreForTests()
  })

  it('redirects an unauthenticated user to login', async () => {
    const logout = vi.fn()
    useAuthStore.setState({
      ensureSession: vi.fn().mockRejectedValue(new AuthRequiredError()),
      logout
    })

    await expect(requireAuth()).rejects.toMatchObject({ status: 302 })
    expect(logout).toHaveBeenCalledOnce()
  })

  it('redirects an authenticated guest away from login', async () => {
    useAuthStore.setState({
      ensureSession: vi.fn().mockResolvedValue({ id: 'user-1', mustChangePassword: false })
    })

    await expectRedirect(requireGuest, '/home')
  })

  it('redirects a user who must change their password to the password-change page', async () => {
    useAuthStore.setState({
      ensureSession: vi.fn().mockResolvedValue({ id: 'user-1', mustChangePassword: true })
    })

    await expectRedirect(requireFullAccess, '/force-change-password')
  })

  it('redirects an authenticated guest who must change their password to the password-change page', async () => {
    useAuthStore.setState({
      ensureSession: vi.fn().mockResolvedValue({ id: 'user-1', mustChangePassword: true })
    })

    await expectRedirect(requireGuest, '/force-change-password')
  })

  it('prioritizes the required password change before the administrator permission check', async () => {
    useAuthStore.setState({
      ensureSession: vi.fn().mockResolvedValue({
        id: 'user-1',
        isSuperAdmin: false,
        mustChangePassword: true
      })
    })

    await expectRedirect(requireAdmin, '/force-change-password')
  })

  it('redirects a non-administrator away from the admin area', async () => {
    useAuthStore.setState({
      ensureSession: vi.fn().mockResolvedValue({
        id: 'user-1',
        isSuperAdmin: false,
        mustChangePassword: false
      })
    })

    await expectRedirect(requireAdmin, '/403')
  })

  it('keeps a user who must change their password on the auth page', async () => {
    useAuthStore.setState({
      ensureSession: vi.fn().mockResolvedValue({ id: 'user-1', mustChangePassword: true })
    })

    await expect(requirePasswordChange()).resolves.toBeNull()
  })
  it('does not log out a new user when an old guard fails late', async () => {
    let reject!: (error: Error) => void
    const logout = vi.fn()
    useAuthStore.setState({
      ensureSession: () =>
        new Promise((_, no) => {
          reject = no
        }),
      logout
    })
    const pending = requireAuth()
    advanceAuthSession()
    useAuthStore.setState({ user: { id: 'B', mustChangePassword: false } as never })
    reject(new Error('old unauthorized'))
    await pending
    expect(logout).not.toHaveBeenCalled()
    expect(useAuthStore.getState().user?.id).toBe('B')
  })
  it('does not log out or redirect on temporary session-check errors', async () => {
    const error = new Error('Network Error')
    const logout = vi.fn()
    useAuthStore.setState({ ensureSession: vi.fn().mockRejectedValue(error), logout })
    await expect(requireAuth()).rejects.toBe(error)
    expect(logout).not.toHaveBeenCalled()
  })
})
