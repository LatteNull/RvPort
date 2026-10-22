import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProjectOverviewContext } from '@/pages/project-detail/ProjectOverviewContext'
import { advanceAuthSession } from '@/store/authSession'
import { createEnvironment, createTestQueryClient } from '@/test/test-utils'

const api = vi.hoisted(() => ({
  createProjectEnvironment: vi.fn(),
  updateProjectEnvironment: vi.fn(),
  testProjectEnvironmentConnection: vi.fn(),
  testSavedProjectEnvironmentConnection: vi.fn(),
  getProjectEnvironments: vi.fn(),
  getProjectEnvironmentScriptExecution: vi.fn(),
  checkProjectEnvironment: vi.fn(),
  runProjectEnvironmentScript: vi.fn()
}))
const { form, feedback } = vi.hoisted(() => ({
  form: {
    validateFields: vi.fn(),
    resetFields: vi.fn(),
    setFieldsValue: vi.fn(),
    setFields: vi.fn()
  },
  feedback: { success: vi.fn(), warning: vi.fn(), error: vi.fn() }
}))
vi.mock('antd', () => ({ Form: { useForm: () => [form] } }))
vi.mock('@/api/project/environments', () => api)
vi.mock('@/utils/feedback', () => ({ feedback }))
import { createEnvironmentFormValues } from './model'
import { useEnvironmentDrawer } from './useEnvironmentDrawer'

const environment = createEnvironment({ credentialId: 'credential-1', username: 'root' })
function setup() {
  const client = createTestQueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <ProjectOverviewContext.Provider
        value={{
          projectId: 'project-1',
          isLoading: false,
          isError: false,
          isFetching: false,
          refetch: vi.fn()
        }}
      >
        {children}
      </ProjectOverviewContext.Provider>
    </QueryClientProvider>
  )
  return {
    client,
    ...renderHook(({ visible }) => useEnvironmentDrawer('project-1', visible, vi.fn()), {
      initialProps: { visible: true },
      wrapper
    })
  }
}

describe('environment submission transaction', () => {
  beforeEach(() => {
    api.getProjectEnvironments.mockResolvedValue({ items: [] })
    api.createProjectEnvironment.mockResolvedValue(environment)
    api.updateProjectEnvironment.mockResolvedValue(environment)
    api.testProjectEnvironmentConnection.mockResolvedValue({})
    form.validateFields.mockResolvedValue(createEnvironmentFormValues(environment))
  })

  it('releases row actions after opening and closing an editor while a check is pending', async () => {
    let finish!: () => void
    api.checkProjectEnvironment.mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          finish = resolve
        })
    )
    const { result } = setup()
    let pending!: Promise<void>
    act(() => {
      pending = result.current.handleCheck(environment)
    })
    act(() => result.current.showEdit(environment))
    await act(async () => {
      finish()
      await pending
    })
    act(() => result.current.showList())
    expect(result.current.checkingEnvironmentId).toBeNull()
    await act(async () => {
      await result.current.handleCheck(environment)
    })
    expect(api.checkProjectEnvironment).toHaveBeenCalledTimes(2)
  })

  it.each(['success', 'failure'])(
    'keeps the save locked until verification submission %s, then refreshes and closes once',
    async (outcome) => {
      const { result, client } = setup()
      form.validateFields.mockResolvedValue({
        ...createEnvironmentFormValues(environment),
        credentialMode: 'replace',
        privateKey: 'new-key'
      })
      act(() => result.current.showCreate())
      await act(async () => {
        await result.current.handleTestConnection()
      })
      let finish!: () => void
      api.testSavedProjectEnvironmentConnection.mockImplementation(
        () =>
          new Promise<void>((yes, no) => {
            finish = () => (outcome === 'success' ? yes() : no(new Error('submit failed')))
          })
      )
      const refresh = vi.spyOn(client, 'invalidateQueries')
      let pending!: Promise<void>
      act(() => {
        pending = result.current.handleSave()
      })
      await waitFor(() => expect(api.testSavedProjectEnvironmentConnection).toHaveBeenCalledOnce())
      expect(result.current.isSaving).toBe(true)
      act(() => {
        result.current.showList()
        void result.current.handleSave()
        void result.current.handleTestConnection()
      })
      expect(result.current.view.type).toBe('create')
      expect(api.createProjectEnvironment).toHaveBeenCalledOnce()
      await act(async () => {
        finish()
        await pending
      })
      expect(result.current.busy).toBe(false)
      expect(result.current.view.type).toBe('list')
      expect(refresh).toHaveBeenCalled()
      if (outcome === 'failure') {
        expect(feedback.warning).toHaveBeenCalledOnce()
        expect(feedback.success).toHaveBeenCalledTimes(1)
      } else expect(feedback.success).toHaveBeenLastCalledWith('环境已保存，连接验证已提交')
    }
  )

  it.each(['edit', 'close', 'auth'])('ignores old save completion after %s', async (change) => {
    const { result, rerender } = setup()
    let finish!: (value: typeof environment) => void
    api.updateProjectEnvironment.mockImplementation(
      () =>
        new Promise((yes) => {
          finish = yes
        })
    )
    act(() => result.current.showEdit(environment))
    let pending!: Promise<void>
    act(() => {
      pending = result.current.handleSave()
    })
    await waitFor(() => expect(api.updateProjectEnvironment).toHaveBeenCalledOnce())
    if (change === 'edit') act(() => result.current.showEdit({ ...environment, id: 'env-2' }))
    else if (change === 'close') {
      rerender({ visible: false })
      rerender({ visible: true })
    } else act(() => advanceAuthSession())
    await act(async () => {
      finish(environment)
      await pending
    })
    expect(feedback.success).not.toHaveBeenCalled()
    expect(api.testSavedProjectEnvironmentConnection).not.toHaveBeenCalled()
    if (change === 'edit')
      expect(result.current.view).toMatchObject({ type: 'edit', environment: { id: 'env-2' } })
  })

  it.each(['validate', 'save', 'precheck', 'script'])(
    'keeps the input and unlocks when %s fails',
    async (failure) => {
      const { result } = setup()
      act(() => result.current.showEdit(environment))
      if (failure === 'validate') form.validateFields.mockRejectedValue(new Error('validation'))
      else if (failure === 'save') api.updateProjectEnvironment.mockRejectedValue(new Error('save'))
      else if (failure === 'precheck')
        api.testProjectEnvironmentConnection.mockRejectedValue(new Error('precheck'))
      else {
        act(() => result.current.showRunScript(environment))
        api.runProjectEnvironmentScript.mockRejectedValue(new Error('script'))
      }
      const resetCount = form.resetFields.mock.calls.length
      await act(async () => {
        await expect(
          failure === 'precheck'
            ? result.current.handleTestConnection()
            : failure === 'script'
              ? result.current.handleRunScript()
              : result.current.handleSave()
        ).rejects.toThrow()
      })
      expect(result.current.busy).toBe(false)
      expect(form.resetFields).toHaveBeenCalledTimes(resetCount)
      expect(result.current.view.type).toBe(failure === 'script' ? 'script' : 'edit')
    }
  )

  it('invalidates precheck after editing and rejects a precheck from an old form', async () => {
    const { result } = setup()
    act(() => result.current.showEdit(environment))
    await act(async () => {
      await result.current.handleTestConnection()
    })
    act(() => result.current.handleEnvironmentFormValuesChange())
    await act(async () => {
      await result.current.handleSave()
    })
    expect(api.testSavedProjectEnvironmentConnection).not.toHaveBeenCalled()
    act(() => result.current.showEdit(environment))
    let finish!: () => void
    api.testProjectEnvironmentConnection.mockImplementation(
      () =>
        new Promise<void>((yes) => {
          finish = yes
        })
    )
    let pending!: Promise<void>
    act(() => {
      pending = result.current.handleTestConnection()
    })
    await waitFor(() => expect(api.testProjectEnvironmentConnection).toHaveBeenCalledTimes(2))
    act(() => result.current.showEdit({ ...environment, id: 'env-2' }))
    await act(async () => {
      finish()
      await pending
    })
    await act(async () => {
      await result.current.handleSave()
    })
    expect(api.testSavedProjectEnvironmentConnection).not.toHaveBeenCalled()
  })
})
