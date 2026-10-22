import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'

import { ProjectOverviewContext } from '@/pages/project-detail/ProjectOverviewContext'
import { useProjectOverview } from '@/pages/project-detail/useProjectOverview'

import { createTestQueryClient } from './test-utils'

export function renderWithProjectOverview(ui: ReactElement, queryClient = createTestQueryClient()) {
  function TestProjectOverviewBoundary({
    children,
    projectId = 'project-1'
  }: {
    children: ReactNode
    projectId?: string
  }) {
    const query = useProjectOverview(projectId)
    return (
      <ProjectOverviewContext.Provider value={{ ...query, projectId }}>
        {children}
      </ProjectOverviewContext.Provider>
    )
  }

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <TestProjectOverviewBoundary>{children}</TestProjectOverviewBoundary>
      </QueryClientProvider>
    )
  }
  return { queryClient, ...render(ui, { wrapper: Wrapper }) }
}
