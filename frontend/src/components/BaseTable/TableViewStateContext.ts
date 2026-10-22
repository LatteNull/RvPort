import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { hashKey, type QueryKey } from '@tanstack/react-query'

export const TableViewStateContext = createContext<Map<string, unknown> | undefined>(undefined)
export const TableViewStateActiveContext = createContext(true)

// Only list view controls are retained, not rows, selections or mounted query subscriptions.
export function useTableViewState<T>(queryKey: QueryKey, initialValue: T) {
  const scope = useContext(TableViewStateContext)
  const key = hashKey(queryKey)
  const [state, setState] = useState(() => ({
    key,
    scope,
    value: (scope?.get(key) as T | undefined) ?? initialValue
  }))
  let value = state.value
  if (key !== state.key || scope !== state.scope) {
    // Keep the closing view intact; restore/reset controls only when a scope opens again.
    value =
      !scope && state.scope && key === state.key
        ? state.value
        : ((scope?.get(key) as T | undefined) ?? initialValue)
    setState({ key, scope, value })
  }
  useEffect(() => {
    scope?.set(key, value)
  }, [key, scope, value])

  const update = useCallback(
    (updater: (current: T) => T) => {
      setState((current) => ({ key, scope, value: updater(current.value) }))
    },
    [key, scope]
  )
  return [value, update] as const
}
