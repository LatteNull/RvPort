import { useCallback, useEffect, useRef } from 'react'
import type { NavigateOptions } from 'react-router'

import type { ProjectView } from './projectView'

export function useProjectViewTransition() {
  const activeTransitionRef = useRef<ViewTransition | null>(null)

  useEffect(
    () => () => {
      activeTransitionRef.current?.skipTransition()
      delete document.documentElement.dataset.projectViewTransition
    },
    []
  )

  return useCallback(
    (
      targetView: ProjectView,
      navigateView: (options: NavigateOptions) => void,
      canAnimate = true
    ) => {
      activeTransitionRef.current?.skipTransition()

      const shouldAnimate =
        canAnimate &&
        typeof document.startViewTransition === 'function' &&
        !window.matchMedia('(prefers-reduced-motion: reduce)').matches

      if (!shouldAnimate) {
        delete document.documentElement.dataset.projectViewTransition
        navigateView({ flushSync: true, viewTransition: false })
        return
      }

      document.documentElement.dataset.projectViewTransition = targetView
      const transition = document.startViewTransition(() => {
        navigateView({ flushSync: true, viewTransition: false })
      })
      activeTransitionRef.current = transition

      const clearTransition = () => {
        if (activeTransitionRef.current !== transition) return
        activeTransitionRef.current = null
        delete document.documentElement.dataset.projectViewTransition
      }
      void transition.finished.then(clearTransition, clearTransition)
    },
    []
  )
}
