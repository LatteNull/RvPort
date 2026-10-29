import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'

import { normalizeKnowledgeBaseSeverity, renderFindingStatusTag, renderSeverityTag } from './tags'

it.each([
  ['CRITICAL', '严重'],
  ['HIGH', '高'],
  ['MEDIUM', '中'],
  ['LOW', '低'],
  ['INFO', '提示'],
  ['legacy', 'legacy'],
  ['', ''],
  [null, '--']
] as const)('renders severity %s without misclassifying unknown values', (value, label) => {
  const view = render(<div>{renderSeverityTag(value)}</div>)
  expect(view.container.textContent).toBe(label)
  expect(normalizeKnowledgeBaseSeverity(value)).toBe(
    value && !['legacy'].includes(value) ? value.toLowerCase() : undefined
  )
})
it.each([
  ['DETECTED', '已发现'],
  ['SUPPRESSED', '已抑制'],
  ['UNKNOWN', 'UNKNOWN'],
  [null, '--']
] as const)('renders status %s preserving unknown states', (value, label) => {
  render(<div>{renderFindingStatusTag(value)}</div>)
  expect(screen.getByText(label)).toBeInTheDocument()
})
