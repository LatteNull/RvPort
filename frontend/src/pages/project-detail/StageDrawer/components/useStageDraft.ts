import { useEffect, useState } from 'react'

// Only track draft equality; route blocking stays at the project page.
export function useStageDraft<T>(
  values: T,
  initialValues: T,
  enabled: boolean,
  onDirtyChange?: (dirty: boolean) => void
) {
  const snapshot = JSON.stringify(values)
  const initialSnapshot = JSON.stringify(initialValues)
  const [submittedSnapshot, setSubmittedSnapshot] = useState<string>()
  const dirty = enabled && snapshot !== initialSnapshot && snapshot !== submittedSnapshot

  useEffect(() => {
    onDirtyChange?.(dirty)
  }, [dirty, onDirtyChange])
  useEffect(() => () => onDirtyChange?.(false), [onDirtyChange])

  return {
    dirty,
    // Capture the submitted render, so edits made during a request remain dirty.
    markSubmitted: () => setSubmittedSnapshot(snapshot),
    resetSubmitted: () => setSubmittedSnapshot(undefined)
  }
}
