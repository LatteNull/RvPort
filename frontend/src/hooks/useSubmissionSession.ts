import { useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import { isAxiosError } from 'axios'

import {
  getAuthGeneration,
  isAuthGenerationCurrent,
  subscribeAuthSession
} from '@/store/authSession'

interface SubmissionScope {
  token: symbol
  active: boolean
  busy: boolean
}

export function useSubmissionSession(key: string, active = true) {
  const generation = useSyncExternalStore(
    subscribeAuthSession,
    getAuthGeneration,
    getAuthGeneration
  )
  const token = useMemo(() => Symbol(`${key}:${active}:${generation}`), [key, active, generation])
  const scopeRef = useRef<SubmissionScope | null>(null)
  const [pendingToken, setPendingToken] = useState<symbol>()
  useLayoutEffect(() => {
    const scope: SubmissionScope = { token, active, busy: false }
    scopeRef.current = scope
    return () => {
      scope.active = false
    }
  }, [active, token])
  const capture = () => {
    const scope = scopeRef.current
    return () =>
      Boolean(
        scope?.active &&
        scope.token === token &&
        scopeRef.current === scope &&
        isAuthGenerationCurrent(generation)
      )
  }
  return {
    token,
    busy: pendingToken === token,
    capture,
    isBusy: () => Boolean(scopeRef.current?.busy),
    run: async <T>(action: (isCurrent: () => boolean) => Promise<T>) => {
      const scope = scopeRef.current
      if (
        !scope?.active ||
        scope.token !== token ||
        !isAuthGenerationCurrent(generation) ||
        scope.busy
      )
        return
      const isCurrent = capture()
      scope.busy = true
      setPendingToken(token)
      try {
        return await action(isCurrent)
      } catch (error) {
        if (
          !isCurrent() ||
          isAxiosError(error) ||
          (error instanceof Error && error.name === 'SessionChangedError') ||
          (error && typeof error === 'object' && 'errorFields' in error)
        )
          return
        throw error
      } finally {
        scope.busy = false
        setPendingToken((current) => (current === token ? undefined : current))
      }
    }
  }
}
