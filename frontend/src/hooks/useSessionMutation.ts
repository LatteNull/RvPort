import { useMutation } from '@tanstack/react-query'
import { isAxiosError } from 'axios'

import { SessionChangedError } from '@/store/authSession'
import { feedback } from '@/utils/feedback'

import { useSubmissionSession } from './useSubmissionSession'

type Success<TData, TVariables> = (
  data: TData,
  variables: TVariables,
  isCurrent: () => boolean
) => void | Promise<void>

// 锁定整个业务提交；多步写入在每次 await 后检查 isCurrent。
export function useSessionMutation<TData, TVariables = void>({
  sessionKey,
  active,
  mutationFn,
  onMutate,
  onSuccess,
  onError,
  onSettled
}: {
  sessionKey: string
  active: boolean
  mutationFn: (variables: TVariables, isCurrent: () => boolean) => Promise<TData>
  onMutate?: (variables: TVariables) => void
  onSuccess?: Success<TData, TVariables>
  onError?: (error: unknown, variables: TVariables) => void
  onSettled?: (data: TData | undefined, error: unknown, variables: TVariables) => void
}) {
  const session = useSubmissionSession(sessionKey, active)
  const mutation = useMutation({
    mutationFn: ({ variables, isCurrent }: { variables: TVariables; isCurrent: () => boolean }) => {
      if (!isCurrent()) throw new SessionChangedError()
      return mutationFn(variables, isCurrent)
    }
  })
  const mutateAsync = (
    variables: TVariables,
    options?: { onSuccess?: Success<TData, TVariables> }
  ) =>
    session.run(async (isCurrent) => {
      let data: TData | undefined
      let failure: unknown
      try {
        onMutate?.(variables)
        data = await mutation.mutateAsync({ variables, isCurrent })
        if (isCurrent()) await onSuccess?.(data, variables, isCurrent)
        if (isCurrent()) await options?.onSuccess?.(data, variables, isCurrent)
        return data
      } catch (error) {
        failure = error
        if (!isCurrent() || error instanceof SessionChangedError) return
        if (onError) onError(error, variables)
        else if (!isAxiosError(error))
          feedback.error(error instanceof Error ? error.message : '提交失败，请重试')
      } finally {
        if (isCurrent()) onSettled?.(data, failure, variables)
      }
    })
  return {
    token: session.token,
    isPending: session.busy,
    variables: mutation.variables?.variables,
    mutateAsync,
    mutate: (variables: TVariables, options?: { onSuccess?: Success<TData, TVariables> }) => {
      void mutateAsync(variables, options)
    }
  }
}
