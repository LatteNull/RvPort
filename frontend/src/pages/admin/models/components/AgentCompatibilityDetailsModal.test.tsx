import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '@/test/test-utils'
import type { ModelProfileAgentProbeResult } from '@/types/admin/models'

import AgentCompatibilityDetailsModal from './AgentCompatibilityDetailsModal'

const result: ModelProfileAgentProbeResult = {
  id: 'result-1',
  runId: 'run-1',
  modelProfileId: 'profile-1',
  agentRuntimeId: 'agent-1',
  agentType: 'CODEX',
  status: 'SUCCESS',
  basicAvailable: true,
  agentCompatible: true,
  checks: [],
  details: {},
  errorCode: null,
  message: '测试完成',
  startedAt: null,
  finishedAt: null,
  durationMs: null,
  createdAt: '2026-09-14T00:00:00Z',
  updatedAt: '2026-09-14T00:00:00Z'
}

function renderResult(overrides: Partial<ModelProfileAgentProbeResult> = {}) {
  return renderWithQueryClient(
    <AgentCompatibilityDetailsModal
      items={[{ agent: { name: 'Codex', type: 'CODEX' }, result: { ...result, ...overrides } }]}
      onCancel={vi.fn()}
    />
  )
}

describe('Agent compatibility details', () => {
  it('displays successful stage-independent results without legacy capability fields', () => {
    renderResult()

    expect(screen.getByText('基础响应')).toBeInTheDocument()
    expect(screen.getByText('Agent 兼容性')).toBeInTheDocument()
    expect(screen.getAllByText('通过')).toHaveLength(2)
    expect(screen.queryByText('未通过')).not.toBeInTheDocument()
    expect(screen.queryByText('测试结果比较')).not.toBeInTheDocument()
    expect(screen.queryByText('知识库 AI 扩展')).not.toBeInTheDocument()
    expect(screen.queryByText('测试说明')).not.toBeInTheDocument()
  })

  it('shows a workspace failure even when the basic response succeeds', () => {
    renderResult({ agentCompatible: false, status: 'FAILED', message: '工作区写入失败' })

    expect(screen.getAllByText('通过')).toHaveLength(1)
    expect(screen.getAllByText('未通过')).toHaveLength(1)
    expect(screen.getByText('工作区写入失败')).toBeInTheDocument()
  })
})
