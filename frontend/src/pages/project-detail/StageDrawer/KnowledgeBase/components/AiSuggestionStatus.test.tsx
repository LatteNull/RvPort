import { render, screen } from '@testing-library/react'
import type { ComponentProps } from 'react'
import { describe, expect, it, vi } from 'vitest'

import type {
  KnowledgeBaseAiExtensionRun,
  KnowledgeBaseAiExtensionStatus
} from '@/types/project/knowledge-base'

import { AiSuggestionStatus } from './AiSuggestionStatus'

function run(status: KnowledgeBaseAiExtensionStatus): KnowledgeBaseAiExtensionRun {
  return {
    agentOutputArtifactId: null,
    agentRuntimeId: 'runtime-1',
    createdAt: '2026-09-11T06:00:00Z',
    finishedAt: null,
    id: 'ai-run-1',
    inputArtifactId: null,
    kbScanRunId: 'scan-1',
    modelProfileId: 'model-1',
    outputArtifactId: null,
    projectId: 'project-1',
    sourceRevisionId: 'revision-1',
    startedAt: null,
    status,
    summary: { validResultCount: 3 },
    taskId: 'task-1',
    updatedAt: '2026-09-11T06:00:00Z'
  }
}

function renderStatus(overrides: Partial<ComponentProps<typeof AiSuggestionStatus>> = {}) {
  render(
    <AiSuggestionStatus
      creating={false}
      error={false}
      loading={false}
      readiness={{
        findingCount: 3,
        kbScanRunId: 'scan-1',
        model: {},
        modelConfigured: true,
        ready: true,
        reason: null
      }}
      onGenerate={vi.fn()}
      onRetry={vi.fn()}
      {...overrides}
    />
  )
}

describe('AiSuggestionStatus', () => {
  it.each([
    ['QUEUED', '排队中', '生成中'],
    ['RUNNING', '生成中', '生成中'],
    ['SUCCEEDED', '已生成', '重新生成'],
    ['PARTIAL_SUCCESS', '部分完成', '重新生成'],
    ['FAILED', '生成失败', '重新生成'],
    ['TIMEOUT', '已超时', '重新生成']
  ] as const)('renders the %s run state', (status, label, action) => {
    renderStatus({ run: run(status) })

    expect(screen.getAllByText(label).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: action })).toBeInTheDocument()
  })

  it('offers a retry when state loading fails', () => {
    renderStatus({ error: true })

    expect(screen.getByText('状态加载失败')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重新读取' })).toBeInTheDocument()
  })
})
