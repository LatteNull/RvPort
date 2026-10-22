import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { createEnvironment, renderWithQueryClient } from '@/test/test-utils'

const { getProjectEnvironments } = vi.hoisted(() => ({
  getProjectEnvironments: vi.fn()
}))

vi.mock('@/api/project/environments', () => ({ getProjectEnvironments }))

import List from './List'

function createListActions(overrides = {}) {
  return {
    checkingEnvironmentId: null,
    onCheck: vi.fn(async () => {}),
    onCreate: vi.fn(),
    onEdit: vi.fn(),
    onHistory: vi.fn(),
    onRefresh: vi.fn(async () => {}),
    onRunScript: vi.fn(),
    onSetCurrent: vi.fn(async () => {}),
    settingRuntimeEnvironmentId: null,
    ...overrides
  }
}

describe('Environment list', () => {
  it('places refresh with the environment list actions', async () => {
    const onRefresh = vi.fn(async () => {})
    getProjectEnvironments.mockResolvedValue({
      hasMore: false,
      items: [],
      page: 1,
      pageSize: 20,
      total: 0
    })
    const user = userEvent.setup()
    renderWithQueryClient(<List actions={createListActions({ onRefresh })} projectId="project-1" />)

    const refreshButton = screen.getByRole('button', { name: '刷新环境列表' })
    const createButton = screen.getByRole('button', { name: /新建环境/ })
    expect(
      refreshButton.compareDocumentPosition(createButton) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy()
    await user.click(refreshButton)
    expect(onRefresh).toHaveBeenCalledOnce()
  })

  it('requests the default list without unsupported filters or sorting', async () => {
    getProjectEnvironments.mockImplementation(async (_projectId, params) => {
      return {
        hasMore: false,
        items: [createEnvironment()],
        page: params.page,
        pageSize: params.pageSize,
        total: 1
      }
    })
    renderWithQueryClient(<List actions={createListActions()} projectId="project-1" />)

    await waitFor(() => expect(screen.getByText('x86-builder')).toBeInTheDocument())
    expect(screen.getByText('apt')).toBeInTheDocument()
    expect(screen.getByText('2026-07-13 08:00')).toBeInTheDocument()
    await waitFor(() =>
      expect(getProjectEnvironments).toHaveBeenLastCalledWith('project-1', {
        page: 1,
        pageSize: 20,
        sortBy: undefined,
        sortOrder: undefined
      })
    )
  })

  it('confirms and submits an environment check from the list action', async () => {
    const onCheck = vi.fn(async () => {})
    getProjectEnvironments.mockResolvedValue({
      hasMore: false,
      items: [createEnvironment()],
      page: 1,
      pageSize: 20,
      total: 1
    })
    const user = userEvent.setup()
    renderWithQueryClient(<List actions={createListActions({ onCheck })} projectId="project-1" />)

    await user.click(await screen.findByRole('button', { name: '环境检查' }))
    await user.click(await screen.findByRole('button', { name: '开始检查' }))

    expect(onCheck).toHaveBeenCalledWith(expect.objectContaining({ id: 'env-1' }))
    expect(getProjectEnvironments).toHaveBeenCalledTimes(1)
  })

  it('allows an enabled environment to run scripts without a previous check', async () => {
    const onRunScript = vi.fn()
    const environment = createEnvironment({ basicInfo: null, connectionStatus: 'UNKNOWN' })
    getProjectEnvironments.mockResolvedValue({
      hasMore: false,
      items: [environment],
      page: 1,
      pageSize: 20,
      total: 1
    })
    renderWithQueryClient(
      <List actions={createListActions({ onRunScript })} projectId="project-1" />
    )

    const button = await screen.findByRole('button', { name: '运行脚本' })
    expect(button).toBeEnabled()
    fireEvent.click(button)
    expect(onRunScript).toHaveBeenCalledWith(environment)
  })

  it('prevents disabled environments from running scripts even with a successful check', async () => {
    getProjectEnvironments.mockResolvedValue({
      hasMore: false,
      items: [createEnvironment({ enabled: false, connectionStatus: 'SUCCESS' })],
      page: 1,
      pageSize: 20,
      total: 1
    })
    renderWithQueryClient(<List actions={createListActions()} projectId="project-1" />)

    expect(await screen.findByRole('button', { name: '运行脚本' })).toBeDisabled()
  })

  it('sets an available environment as the current role from the table', async () => {
    const onSetCurrent = vi.fn(async () => {})
    getProjectEnvironments.mockResolvedValue({
      hasMore: false,
      items: [createEnvironment()],
      page: 1,
      pageSize: 20,
      total: 1
    })
    renderWithQueryClient(
      <List
        actions={createListActions({ onSetCurrent })}
        projectId="project-1"
        runtimeEnvironments={{
          missing: ['SOURCE'],
          projectId: 'project-1',
          ready: false,
          sourceEnvironment: null,
          targetEnvironment: null,
          updatedBy: null,
          updatedAt: null,
          version: 0
        }}
      />
    )

    const setCurrentButton = await screen.findByRole('button', { name: '设为当前源环境' })
    const checkButton = screen.getByRole('button', { name: '环境检查' })
    expect(
      checkButton.compareDocumentPosition(setCurrentButton) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy()

    fireEvent.click(setCurrentButton)
    fireEvent.click(await screen.findByRole('button', { name: '确认设置' }))

    await waitFor(() =>
      expect(onSetCurrent).toHaveBeenCalledWith(expect.objectContaining({ id: 'env-1' }))
    )
  })

  it('shows the selected role and disables unavailable candidates', async () => {
    getProjectEnvironments.mockResolvedValue({
      hasMore: false,
      items: [
        createEnvironment(),
        createEnvironment({ connectionStatus: 'UNKNOWN', id: 'env-2', name: 'standby' })
      ],
      page: 1,
      pageSize: 20,
      total: 2
    })
    renderWithQueryClient(
      <List
        actions={createListActions()}
        projectId="project-1"
        runtimeEnvironments={{
          missing: ['TARGET'],
          projectId: 'project-1',
          ready: false,
          sourceEnvironment: {
            architecture: 'x86_64',
            connectionStatus: 'SUCCESS',
            enabled: true,
            configVersion: 1,
            id: 'env-1',
            name: 'x86-builder',
            role: 'SOURCE'
          },
          targetEnvironment: null,
          updatedBy: null,
          updatedAt: null,
          version: 1
        }}
      />
    )

    expect(await screen.findByLabelText('当前源环境')).toHaveAttribute('data-visual', 'outlined')
    expect(screen.getByRole('button', { name: '设为当前源环境' })).toBeDisabled()
    expect(screen.queryByRole('columnheader', { name: '当前配置' })).not.toBeInTheDocument()
  })
})
