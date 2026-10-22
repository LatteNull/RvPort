import { isAxiosError } from 'axios'
import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

import type { User } from '@/types'
import { safeLocalStorage } from '@/utils/localStorage'

import {
  advanceAuthSession,
  getAuthGeneration,
  isAuthGenerationCurrent,
  SessionChangedError
} from './authSession'

const SESSION_CHECK_TTL_MS = 60_000
export class AuthRequiredError extends Error {
  constructor() {
    super('AUTH_REQUIRED')
  }
}
const AUTH_REQUIRED_ERROR = new AuthRequiredError()

interface AuthState {
  user: User | null
  sessionCheckedAt: number | null
  setUser: (user: User | null) => void
  refreshUser: () => Promise<User>
  ensureSession: () => Promise<User>
  logout: () => void
}

let sessionPromise: { generation: number; promise: Promise<User> } | null = null

export function resetAuthStoreForTests() {
  sessionPromise = null
  advanceAuthSession()
  useAuthStore.setState({ user: null, sessionCheckedAt: null })
  useAuthStore.persist.clearStorage()
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      sessionCheckedAt: null,
      setUser: (user) => {
        if (get().user?.id !== user?.id) advanceAuthSession()
        set({ user, sessionCheckedAt: user ? Date.now() : null })
      },
      refreshUser: async () => {
        const generation = getAuthGeneration()
        const { getMe } = await import('@/api/auth')
        if (!isAuthGenerationCurrent(generation)) throw new SessionChangedError()
        try {
          const user = await getMe()
          if (!isAuthGenerationCurrent(generation)) throw new SessionChangedError()
          get().setUser(user)
          return user
        } catch (error) {
          if (!isAuthGenerationCurrent(generation)) throw new SessionChangedError()
          if (isAxiosError(error) && error.response?.status === 401) get().logout()
          throw error
        }
      },
      ensureSession: async () => {
        const { user, sessionCheckedAt, refreshUser } = get()
        if (sessionCheckedAt && Date.now() - sessionCheckedAt < SESSION_CHECK_TTL_MS) {
          if (user) return user
          throw AUTH_REQUIRED_ERROR
        }

        const generation = getAuthGeneration()
        if (!sessionPromise || sessionPromise.generation !== generation) {
          const pending = { generation, promise: refreshUser() }
          sessionPromise = pending
          void pending.promise
            .finally(() => {
              if (sessionPromise === pending) sessionPromise = null
            })
            .catch(() => undefined)
        }
        return sessionPromise.promise
      },
      logout: () => {
        advanceAuthSession()
        set({ user: null, sessionCheckedAt: Date.now() })
      }
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => safeLocalStorage),
      partialize: (state) => ({
        user: state.user
      })
    }
  )
)
