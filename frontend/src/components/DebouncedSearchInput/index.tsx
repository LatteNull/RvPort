import { useContext, useEffect, useId, useRef } from 'react'
import { SearchOutlined } from '@ant-design/icons'
import type { QueryKey } from '@tanstack/react-query'
import type { InputProps } from 'antd'
import { Input } from 'antd'

import { TableViewStateActiveContext, useTableViewState } from '../BaseTable/TableViewStateContext'

const DEFAULT_DEBOUNCE_MS = 300

export interface DebouncedSearchInputProps extends Omit<
  InputProps,
  'onChange' | 'onPressEnter' | 'prefix' | 'value'
> {
  debounceMs?: number
  draftStateKey?: QueryKey
  /** Increment to discard an unapplied draft, even when value itself has not changed. */
  resetKey?: number
  onSearch: (value: string) => void
  value?: string
}

export default function DebouncedSearchInput({
  allowClear = true,
  debounceMs = DEFAULT_DEBOUNCE_MS,
  draftStateKey,
  resetKey = 0,
  onClear,
  onSearch,
  value = '',
  ...props
}: DebouncedSearchInputProps) {
  const instanceId = useId()
  const active = useContext(TableViewStateActiveContext)
  const [draftState, setDraftState] = useTableViewState(
    draftStateKey ?? ['search-input', instanceId],
    {
      draftValue: value,
      externalValue: value,
      resetKey,
      pending: false
    }
  )
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const onSearchRef = useRef(onSearch)
  let draftValue = draftState.draftValue

  if (value !== draftState.externalValue || resetKey !== draftState.resetKey) {
    draftValue = value
    setDraftState(() => ({ draftValue: value, externalValue: value, resetKey, pending: false }))
  }

  useEffect(() => {
    onSearchRef.current = onSearch
  }, [onSearch])

  useEffect(() => {
    if (!active || !draftState.pending) return
    // A retained, unapplied draft resumes debounce when the list is mounted again.
    const timer = setTimeout(() => {
      timerRef.current = undefined
      setDraftState((current) => ({ ...current, pending: false }))
      onSearchRef.current(draftValue.trim())
    }, debounceMs)
    timerRef.current = timer
    return () => {
      clearTimeout(timer)
      if (timerRef.current === timer) timerRef.current = undefined
    }
  }, [active, debounceMs, draftState.pending, draftValue, setDraftState])

  const cancelPendingSearch = () => {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = undefined
  }
  const submitSearch = (nextValue: string) => {
    cancelPendingSearch()
    setDraftState((current) => ({ ...current, pending: false }))
    onSearchRef.current(nextValue.trim())
  }

  return (
    <Input
      {...props}
      allowClear={allowClear}
      prefix={
        <SearchOutlined aria-hidden="true" style={{ color: 'var(--ant-color-text-placeholder)' }} />
      }
      value={draftValue}
      onChange={(event) => {
        const nextValue = event.target.value
        setDraftState(() => ({
          draftValue: nextValue,
          externalValue: value,
          resetKey,
          pending: true
        }))
      }}
      onClear={() => {
        setDraftState(() => ({ draftValue: '', externalValue: value, resetKey, pending: false }))
        submitSearch('')
        onClear?.()
      }}
      onPressEnter={(event) => submitSearch(event.currentTarget.value)}
    />
  )
}
