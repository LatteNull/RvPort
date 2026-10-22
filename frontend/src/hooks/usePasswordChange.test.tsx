import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/store/authStore'

const { changePassword, logout, warning } = vi.hoisted(() => ({
  changePassword: vi.fn(),
  logout: vi.fn(),
  warning: vi.fn()
}))
vi.mock('@/api/auth', () => ({ changePassword, logout }))
vi.mock('@/utils/feedback', () => ({ feedback: { success: vi.fn(), warning } }))
import { usePasswordChange } from './usePasswordChange'

const user = {
  id: 'A',
  username: 'qa',
  displayName: null,
  email: null,
  isSuperAdmin: false,
  mustChangePassword: true,
  status: 'ACTIVE' as const,
  lastLoginAt: null,
  createdAt: '2026-09-29',
  updatedAt: null
}

describe('confirmed logout after password change', () => {
  beforeEach(() => {
    useAuthStore.getState().setUser(user)
    changePassword.mockResolvedValue({})
  })
  it.each(['false', 'error'])(
    'keeps the session on logout %s and retries only logout',
    async (failure) => {
      if (failure === 'false') logout.mockResolvedValueOnce({ loggedOut: false })
      else logout.mockRejectedValueOnce(new Error('offline'))
      logout.mockResolvedValueOnce({ loggedOut: true })
      const done = vi.fn()
      const { result } = renderHook(() => usePasswordChange(done))
      await act(async () => {
        await result.current.submit({ currentPassword: 'qa-old', newPassword: 'qa-new' })
      })
      expect(result.current.passwordChanged).toBe(true)
      expect(result.current.loading).toBe(false)
      expect(useAuthStore.getState().user?.id).toBe('A')
      expect(done).not.toHaveBeenCalled()
      expect(warning).toHaveBeenCalledOnce()
      await act(async () => {
        await result.current.submit()
      })
      expect(changePassword).toHaveBeenCalledOnce()
      expect(logout).toHaveBeenCalledTimes(2)
      expect(useAuthStore.getState().user).toBeNull()
      expect(done).toHaveBeenCalledOnce()
    }
  )
  it('does not log out B after A completes a delayed password change', async () => {
    let finish!: () => void
    changePassword.mockImplementation(
      () =>
        new Promise<void>((yes) => {
          finish = yes
        })
    )
    const done = vi.fn()
    const { result } = renderHook(() => usePasswordChange(done))
    let pending!: Promise<void>
    act(() => {
      pending = result.current.submit({ currentPassword: 'qa-old', newPassword: 'qa-new' })
    })
    act(() => useAuthStore.getState().setUser({ ...user, id: 'B' }))
    await act(async () => {
      finish()
      await pending
    })
    expect(logout).not.toHaveBeenCalled()
    expect(done).not.toHaveBeenCalled()
    expect(useAuthStore.getState().user?.id).toBe('B')
    expect(result.current.passwordChanged).toBe(false)
  })
})
