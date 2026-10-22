import {
  getAuthGeneration,
  isAuthGenerationCurrent,
  SessionChangedError
} from '@/store/authSession'
import type { PageResponse } from '@/types'

// 只用于需要完整选项/聚合记录的读取；可见列表仍由服务端分页。
export async function readAllPages<T>(
  fetchPage: (page: number, pageSize: number) => Promise<PageResponse<T>>,
  {
    pageSize = 200,
    signal,
    shouldContinue
  }: { pageSize?: number; signal?: AbortSignal; shouldContinue?: () => boolean } = {}
): Promise<PageResponse<T>> {
  const generation = getAuthGeneration()
  const assertCurrent = () => {
    if (!isAuthGenerationCurrent(generation)) throw new SessionChangedError()
    if (shouldContinue && !shouldContinue()) throw new SessionChangedError()
    signal?.throwIfAborted()
  }
  assertCurrent()
  const first = await fetchPage(1, pageSize)
  assertCurrent()
  const size = first.pageSize > 0 ? first.pageSize : pageSize
  const pageCount = Math.ceil(first.total / size)
  const items = [...first.items]
  for (let page = 2; page <= pageCount; page += 4) {
    assertCurrent()
    const pages = await Promise.all(
      Array.from({ length: Math.min(4, pageCount - page + 1) }, (_, index) =>
        fetchPage(page + index, size)
      )
    )
    assertCurrent()
    items.push(...pages.flatMap((result) => result.items))
  }
  return { ...first, items, hasMore: false }
}
