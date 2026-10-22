import { useState } from 'react'

import { createProjectAutomatedTest } from '@/api/project/automated-test'
import { useSubmissionSession } from '@/hooks/useSubmissionSession'
import type { CreateProjectAutomatedTestRequest } from '@/types/project'
import { feedback } from '@/utils/feedback'

import type { TestBuildContext } from './types'

export type TestBatchInput = Omit<
  CreateProjectAutomatedTestRequest,
  'buildRunId' | 'testBatchId' | 'testBatchRole' | 'workingDirectory'
>
type CreatedTask = Awaited<ReturnType<typeof createProjectAutomatedTest>>
type Role = 'SOURCE' | 'TARGET'
interface Batch {
  id: string
  requests: { role: Role; input: CreateProjectAutomatedTestRequest }[]
  created: Partial<Record<Role, CreatedTask>>
  failed: Role[]
  owner: symbol
  onComplete?: () => void
}

export function useTestBatchSubmission(
  projectId: string | undefined,
  active: boolean,
  contexts: TestBuildContext[]
) {
  const session = useSubmissionSession(`test-batch:${projectId}`, active)
  const [batch, setBatch] = useState<Batch>()
  const currentBatch = batch?.owner === session.token ? batch : undefined

  const execute = async (plan: Batch, isCurrent: () => boolean) => {
    const pending = plan.requests.filter(({ role }) => !plan.created[role])
    const results = await Promise.allSettled(
      pending.map(({ input }) => createProjectAutomatedTest(projectId!, input))
    )
    if (!isCurrent()) return
    const created = { ...plan.created }
    const failed: Role[] = []
    results.forEach((result, index) => {
      const role = pending[index].role
      if (result.status === 'fulfilled') created[role] = result.value
      else failed.push(role)
    })
    const next = { ...plan, created, failed }
    setBatch(next)
    if (failed.length) {
      feedback.warning(
        failed.length === 2
          ? '两侧测试任务均未能确认创建，请重试本批次'
          : '部分测试任务未能确认创建，已提交任务已保留，可重试失败侧'
      )
    } else {
      plan.onComplete?.()
      feedback.success('x86 与 RISC-V 自动化测试已创建')
    }
    return next
  }
  return {
    isPending: session.busy,
    batch: currentBatch,
    submit: (input: TestBatchInput, onComplete?: () => void) =>
      session.run(async (isCurrent) => {
        if (!projectId || currentBatch?.failed.length) return
        // Validate both inputs before starting either side.
        if (contexts.length !== 2 || contexts.some((context) => !context.build)) {
          feedback.error('两侧构建前置条件不满足')
          return
        }
        const id = crypto.randomUUID()
        const plan: Batch = {
          id,
          created: {},
          failed: [],
          owner: session.token,
          onComplete,
          requests: contexts.map(({ role, build }) => ({
            role,
            input: {
              ...input,
              environmentVariables: input.environmentVariables
                ? { ...input.environmentVariables }
                : undefined,
              testBatchId: id,
              testBatchRole: role,
              buildRunId: build!.id,
              workingDirectory: build!.workingDirectory
            }
          }))
        }
        return execute(plan, isCurrent)
      }),
    retry: () =>
      session.run(async (isCurrent) => {
        if (currentBatch?.failed.length) return execute(currentBatch, isCurrent)
      }),
    startNewBatch: () => {
      if (!session.isBusy()) setBatch(undefined)
    }
  }
}
