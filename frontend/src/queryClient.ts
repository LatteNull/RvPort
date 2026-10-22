import { QueryClient } from '@tanstack/react-query'

import { subscribeAuthSession } from '@/store/authSession'

export function isolateAuthQueries(client: QueryClient) {
  return subscribeAuthSession(() => {
    // 先取消再移除旧查询；迟到 API 结果还由请求层的会话归属校验拦截。
    const privateQuery = {
      predicate: (query: { meta?: Record<string, unknown> }) => query.meta?.public !== true
    }
    void client.cancelQueries(privateQuery)
    client.removeQueries(privateQuery)
    client.getMutationCache().clear()
  })
}

export const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 5 * 60 * 1000 } }
})
isolateAuthQueries(queryClient)
