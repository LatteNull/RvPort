import { useEffect, useState } from 'react'
import type { RefObject } from 'react'

interface UseTableViewportHeightOptions {
  enabled?: boolean
  footerRef: RefObject<HTMLElement | null>
  rootRef: RefObject<HTMLElement | null>
  toolbarRef: RefObject<HTMLElement | null>
  viewportRef: RefObject<HTMLElement | null>
}

export function useTableViewportHeight({
  enabled = true,
  footerRef,
  rootRef,
  toolbarRef,
  viewportRef
}: UseTableViewportHeightOptions) {
  const [height, setHeight] = useState<number>()
  useEffect(() => {
    const root = rootRef.current
    if (!enabled || !root) {
      return undefined
    }

    const measure = () => {
      const rootHeight = root.getBoundingClientRect().height
      const toolbarHeight = toolbarRef.current?.getBoundingClientRect().height ?? 0
      const footerHeight = footerRef.current?.getBoundingClientRect().height ?? 0
      const sectionCount = Number(toolbarHeight > 0) + Number(footerHeight > 0)
      const rootStyle = getComputedStyle(root)
      const rootGap = Number.parseFloat(rootStyle.rowGap || rootStyle.gap)
      const gapHeight = Number.isNaN(rootGap) ? 0 : rootGap * sectionCount
      const tableHeaderHeight =
        viewportRef.current?.querySelector<HTMLElement>('.ant-table-thead')?.getBoundingClientRect()
          .height ?? 0
      const tableSummaryHeight =
        viewportRef.current
          ?.querySelector<HTMLElement>('.ant-table-summary')
          ?.getBoundingClientRect().height ?? 0
      const nextHeight = Math.floor(
        rootHeight -
          toolbarHeight -
          footerHeight -
          gapHeight -
          tableHeaderHeight -
          tableSummaryHeight
      )

      const nextViewportHeight = nextHeight > 0 ? nextHeight : undefined
      setHeight((currentHeight) =>
        currentHeight === nextViewportHeight ? currentHeight : nextViewportHeight
      )
    }

    measure()
    const observer =
      typeof ResizeObserver === 'undefined'
        ? undefined
        : new ResizeObserver(() => {
            measure()
          })

    observer?.observe(root)
    if (toolbarRef.current) {
      observer?.observe(toolbarRef.current)
    }
    if (footerRef.current) {
      observer?.observe(footerRef.current)
    }
    const tableChrome = viewportRef.current?.querySelectorAll<HTMLElement>(
      '.ant-table-thead, .ant-table-summary'
    )
    tableChrome?.forEach((element) => observer?.observe(element))
    window.addEventListener('resize', measure)

    return () => {
      observer?.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [enabled, footerRef, rootRef, toolbarRef, viewportRef])

  return height
}
