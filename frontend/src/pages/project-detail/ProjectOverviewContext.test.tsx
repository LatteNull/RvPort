import { useState } from 'react'
import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '@/test/test-utils'
import type { ProjectOverview } from '@/types/project'

const { getProjectOverview } = vi.hoisted(() => ({ getProjectOverview: vi.fn() }))
vi.mock('@/api/project/projects', () => ({ getProjectOverview }))
import { ProjectOverviewContext, useProjectOverviewData } from './ProjectOverviewContext'
import { projectQueryKeys } from './queryKeys'
import { useProjectOverview } from './useProjectOverview'

function Consumer({ name }: { name: string }) {
  const state = useProjectOverviewData('project-1')
  return (
    <section aria-label={name}>
      {state.isError ? (
        <button onClick={() => void state.refetch()}>重试</button>
      ) : (
        (state.data?.project.name ?? 'loading')
      )}
    </section>
  )
}
function Page() {
  const query = useProjectOverview('project-1')
  const [stage, setStage] = useState(true)
  return (
    <ProjectOverviewContext.Provider value={{ ...query, projectId: 'project-1' }}>
      <button onClick={() => setStage(!stage)}>切换阶段</button>
      <Consumer name="page" />
      {stage ? (
        <>
          <Consumer name="assets" />
          <Consumer name="env" />
          <Consumer name="build" />
        </>
      ) : null}
    </ProjectOverviewContext.Provider>
  )
}

describe('one overview owner', () => {
  it('retains exactly one observer across stage switches, cache merges and invalidation', async () => {
    getProjectOverview.mockResolvedValue({ project: { name: 'initial' } })
    const { queryClient } = renderWithQueryClient(<Page />)
    await screen.findAllByText('initial')
    const query = () =>
      queryClient.getQueryCache().find({ queryKey: projectQueryKeys.overview('project-1') })!
    expect(query().getObserversCount()).toBe(1)
    act(() =>
      queryClient.setQueryData<ProjectOverview>(projectQueryKeys.overview('project-1'), (old) => ({
        ...old!,
        project: { ...old!.project, name: 'merged' }
      }))
    )
    await waitFor(() => expect(screen.getAllByText('merged')).toHaveLength(4))
    fireEvent.click(screen.getByText('切换阶段'))
    expect(query().getObserversCount()).toBe(1)
    getProjectOverview.mockResolvedValue({ project: { name: 'SSE refreshed' } })
    await act(async () => {
      await queryClient.invalidateQueries({ queryKey: projectQueryKeys.overview('project-1') })
    })
    await screen.findByText('SSE refreshed')
    fireEvent.click(screen.getByText('切换阶段'))
    expect(screen.getAllByText('SSE refreshed')).toHaveLength(4)
    expect(query().getObserversCount()).toBe(1)
  })

  it('shares first failure and retry recovery without adding observers', async () => {
    getProjectOverview
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValue({ project: { name: 'recovered' } })
    const { queryClient } = renderWithQueryClient(<Page />)
    fireEvent.click((await screen.findAllByText('重试'))[0])
    await waitFor(() => expect(screen.getAllByText('recovered')).toHaveLength(4))
    expect(
      queryClient
        .getQueryCache()
        .find({ queryKey: projectQueryKeys.overview('project-1') })
        ?.getObserversCount()
    ).toBe(1)
  })
})
