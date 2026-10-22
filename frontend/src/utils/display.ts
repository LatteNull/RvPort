export const EMPTY_DISPLAY_VALUE = '--'

const dateTimeFormatter = new Intl.DateTimeFormat('en-CA', {
  day: '2-digit',
  hour: '2-digit',
  hour12: false,
  minute: '2-digit',
  month: '2-digit',
  year: 'numeric'
})

const numberFormatter = new Intl.NumberFormat('zh-CN', {
  maximumFractionDigits: 2,
  minimumFractionDigits: 0
})

export function formatDisplayValue<T>(
  value: T | null | undefined,
  formatter: (value: T) => string = String
) {
  return value == null ? EMPTY_DISPLAY_VALUE : formatter(value)
}

export function formatDateTime(value: string | null | undefined) {
  if (value == null) return EMPTY_DISPLAY_VALUE

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return EMPTY_DISPLAY_VALUE

  const parts = Object.fromEntries(
    dateTimeFormatter
      .formatToParts(date)
      .filter((part) => part.type !== 'literal')
      .map((part) => [part.type, part.value])
  )
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`
}

export function formatDateTimeRange({
  finishedAt,
  startedAt
}: {
  finishedAt: string | null | undefined
  startedAt: string | null | undefined
}) {
  const formattedStartedAt = formatDateTime(startedAt)
  const formattedFinishedAt = formatDateTime(finishedAt)

  if (formattedStartedAt === EMPTY_DISPLAY_VALUE) return formattedFinishedAt
  if (formattedFinishedAt === EMPTY_DISPLAY_VALUE) return formattedStartedAt
  if (formattedStartedAt.slice(0, 10) === formattedFinishedAt.slice(0, 10)) {
    return `${formattedStartedAt} - ${formattedFinishedAt.slice(11)}`
  }
  return `${formattedStartedAt} 至 ${formattedFinishedAt}`
}

export function parseEnvironmentVariables(value: string) {
  return value.split('\n').reduce<Record<string, string>>((variables, line) => {
    const separatorIndex = line.indexOf('=')
    if (separatorIndex <= 0) return variables

    const key = line.slice(0, separatorIndex).trim()
    if (key) variables[key] = line.slice(separatorIndex + 1).trim()
    return variables
  }, {})
}

const taskStatusColors: Record<string, 'default' | 'success' | 'error' | 'warning' | 'processing'> =
  {
    SUCCEEDED: 'success',
    FAILED: 'error',
    CANCELLED: 'default',
    TIMEOUT: 'warning'
  }

const taskStatusLabels: Record<string, string> = {
  PENDING: '等待中',
  QUEUED: '排队中',
  RUNNING: '进行中',
  SUCCEEDED: '成功',
  FAILED: '失败',
  CANCELLED: '已取消',
  TIMEOUT: '超时'
}

export function getTaskStatusPresentation(
  status: string | null | undefined,
  options: { fallbackLabel?: string; labels?: Record<string, string> } = {}
) {
  const { fallbackLabel = EMPTY_DISPLAY_VALUE, labels } = options
  return {
    color: status ? (taskStatusColors[status] ?? 'processing') : undefined,
    label:
      (status && labels?.[status]) ??
      (status && taskStatusLabels[status]) ??
      status ??
      fallbackLabel
  }
}

export function formatFileSize(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value) || value < 0) return EMPTY_DISPLAY_VALUE
  if (value < 1024) return `${numberFormatter.format(value)} B`
  if (value < 1024 ** 2) return `${numberFormatter.format(value / 1024)} KB`
  if (value < 1024 ** 3) return `${numberFormatter.format(value / 1024 ** 2)} MB`
  return `${numberFormatter.format(value / 1024 ** 3)} GB`
}

export function toLabelOptions<T extends string>(labels: Record<T, string>) {
  return (Object.keys(labels) as T[]).map((value) => ({ label: labels[value], value }))
}
