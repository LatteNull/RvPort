export function getExecutionStatusText(status: string | undefined) {
  if (status === 'SUCCEEDED') return '已完成'
  if (status === 'FAILED' || status === 'CANCELLED' || status === 'TIMEOUT') return '执行失败'
  if (status === 'RUNNING' || status === 'QUEUED') return '执行中'
  return '待执行'
}
