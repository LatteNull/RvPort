import { useEffect, useEffectEvent } from 'react'

// Only completed, current results may correct a retained page; never placeholder totals.
export function usePageBounds({
  page,
  pageSize,
  total,
  ready,
  onCorrectPage
}: {
  page: number
  pageSize: number
  total?: number
  ready: boolean
  onCorrectPage: (page: number) => void
}) {
  const correctPage = useEffectEvent(onCorrectPage)
  useEffect(() => {
    if (!ready || total === undefined || !Number.isFinite(total) || total < 0 || pageSize <= 0)
      return
    const lastPage = Math.max(1, Math.ceil(total / pageSize))
    if (page > lastPage) correctPage(lastPage)
  }, [page, pageSize, ready, total])
}
