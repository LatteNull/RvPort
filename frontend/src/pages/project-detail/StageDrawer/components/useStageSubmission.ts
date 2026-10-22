import { useState } from 'react'

// 只追踪提交已受理到权威执行身份更新之间的间隙，不伪造运行状态。
export function useStageSubmission(executionId: string | undefined, context: string) {
  const [submitted, setSubmitted] = useState<{ executionId?: string; context: string }>()
  return {
    pending: Boolean(
      submitted && submitted.context === context && submitted.executionId === executionId
    ),
    markSubmitted: () => setSubmitted({ executionId, context }),
    reset: () => setSubmitted(undefined)
  }
}
