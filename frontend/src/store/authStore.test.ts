import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { User } from '@/types'

const { getMe } = vi.hoisted(() => ({ getMe: vi.fn() }))

vi.mock('@/api/auth', () => ({ getMe }))

import { resetAuthStoreForTests, useAuthStore } from './authStore'

const user: User = {
  id: 'user-1',
  username: 'admin',
  displayName: 'Admin',
  email: null,
  isSuperAdmin: true,
  mustChangePassword: false,
  status: 'ACTIVE',
  lastLoginAt: null,
  createdAt: '2026-07-13T00:00:00+08:00',
  updatedAt: null
}

describe('authStore', () => {
  beforeEach(() => {
    resetAuthStoreForTests()
  })

  afterEach(() => {
    resetAuthStoreForTests()
  })

  it('reuses one in-flight session validation', async () => {
    let resolveUser: (value: User) => void = () => undefined
    getMe.mockImplementation(
      () =>
        new Promise<User>((resolve) => {
          resolveUser = resolve
        })
    )

    const first = useAuthStore.getState().ensureSession()
    const second = useAuthStore.getState().ensureSession()
    await vi.waitFor(() => {
      expect(getMe).toHaveBeenCalledOnce()
    })
    resolveUser(user)

    await expect(Promise.all([first, second])).resolves.toEqual([user, user])
    expect(getMe).toHaveBeenCalledTimes(1)
  })

  it('uses a fresh cached session without another request', async () => {
    useAuthStore.getState().setUser(user)

    await expect(useAuthStore.getState().ensureSession()).resolves.toEqual(user)
    expect(getMe).not.toHaveBeenCalled()
  })

  it('clears the user when a session refresh fails', async () => {
    getMe.mockRejectedValue(new Error('unauthorized'))

    await expect(useAuthStore.getState().refreshUser()).rejects.toThrow('unauthorized')
    expect(useAuthStore.getState().user).toBeNull()
  })
  it.each(['success', 'failure'])(
    'ignores a late old refresh %s after an identity switch',
    async (outcome) => {
      let resolve!: (value: User) => void
      let reject!: (error: Error) => void
      getMe.mockImplementation(
        () =>
          new Promise<User>((yes, no) => {
            resolve = yes
            reject = no
          })
      )
      const old = useAuthStore
        .getState()
        .refreshUser()
        .catch((error: Error) => error)
      await vi.waitFor(() => expect(getMe).toHaveBeenCalledOnce())
      const next = { ...user, id: 'user-2', username: 'second' }
      useAuthStore.getState().setUser(next)
      if (outcome === 'success') resolve(user)
      else reject(new Error('old unauthorized'))
      expect(await old).toMatchObject({ name: 'SessionChangedError' })
      expect(useAuthStore.getState().user).toEqual(next)
    }
  )

  it('does not let an old validation finally clear a new session lock', async () => {
    let resolveOld!: (value: User) => void
    let resolveNew!: (value: User) => void
    getMe
      .mockImplementationOnce(
        () =>
          new Promise<User>((resolve) => {
            resolveOld = resolve
          })
      )
      .mockImplementationOnce(
        () =>
          new Promise<User>((resolve) => {
            resolveNew = resolve
          })
      )
    const old = useAuthStore
      .getState()
      .ensureSession()
      .catch(() => null)
    await vi.waitFor(() => expect(getMe).toHaveBeenCalledTimes(1))
    useAuthStore.getState().logout()
    useAuthStore.setState({ sessionCheckedAt: null })
    const next = useAuthStore.getState().ensureSession()
    await vi.waitFor(() => expect(getMe).toHaveBeenCalledTimes(2))
    resolveOld(user)
    await old
    const duplicate = useAuthStore.getState().ensureSession()
    expect(getMe).toHaveBeenCalledTimes(2)
    resolveNew({ ...user, id: 'user-2' })
    await expect(Promise.all([next, duplicate])).resolves.toMatchObject([
      { id: 'user-2' },
      { id: 'user-2' }
    ])
  })
  it('preserves an existing identity on network failure and allows another check', async () => {
    useAuthStore.getState().setUser(user)
    useAuthStore.setState({ sessionCheckedAt: 0 })
    getMe.mockRejectedValueOnce(new Error('Network Error')).mockResolvedValueOnce(user)
    await expect(useAuthStore.getState().ensureSession()).rejects.toThrow('Network Error')
    expect(useAuthStore.getState().user).toEqual(user)
    await expect(useAuthStore.getState().ensureSession()).resolves.toEqual(user)
    expect(getMe).toHaveBeenCalledTimes(2)
  })
  it('does not start an old refresh after the identity changes during module loading', async () => {
    const pending = useAuthStore
      .getState()
      .refreshUser()
      .catch((error: Error) => error)
    useAuthStore.getState().setUser(user)
    expect(await pending).toMatchObject({ name: 'SessionChangedError' })
    expect(getMe).not.toHaveBeenCalled()
  })
})
