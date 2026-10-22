import { useMemo } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'

import { getProjects, type ProjectListParams } from '@/api/project/projects'

export type ProjectListFilters = Pick<ProjectListParams, 'keyword' | 'stage' | 'status'>

export const PROJECT_PAGE_SIZE = 20
export const PROJECTS_QUERY_KEY = ['projects'] as const

export function projectListQueryKey(filters: ProjectListFilters) {
  return [
    ...PROJECTS_QUERY_KEY,
    {
      keyword: filters.keyword || undefined,
      pageSize: PROJECT_PAGE_SIZE,
      stage: filters.stage,
      status: filters.status
    }
  ] as const
}

export function useProjectList(filters: ProjectListFilters) {
  const query = useInfiniteQuery({
    queryKey: projectListQueryKey(filters),
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      getProjects({
        ...filters,
        keyword: filters.keyword || undefined,
        page: pageParam,
        pageSize: PROJECT_PAGE_SIZE
      }),
    getNextPageParam: (lastPage) => (lastPage.hasMore ? lastPage.page + 1 : undefined)
  })
  const projects = useMemo(
    () => query.data?.pages.flatMap((page) => page.items) ?? [],
    [query.data]
  )

  return {
    ...query,
    projects,
    total: query.data?.pages[0]?.total ?? 0
  }
}
