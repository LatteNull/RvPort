import { lazy, Suspense, useState } from 'react'

import type { AgentRuntime, ModelProfileAgentProbeResult } from '@/types/admin/models'

import styles from '../index.module.scss'

function getAgentIdentity(result: ModelProfileAgentProbeResult, agentRuntimes: AgentRuntime[]) {
  const runtime = agentRuntimes.find((item) => item.id === result.agentRuntimeId)

  return {
    name: runtime?.name ?? result.agentType,
    type: runtime?.agentType ?? result.agentType
  }
}

export interface PreparedCompatibilityResult {
  agent: ReturnType<typeof getAgentIdentity>
  result: ModelProfileAgentProbeResult
}

const AgentCompatibilityDetailsModal = lazy(() => import('./AgentCompatibilityDetailsModal'))

export default function AgentCompatibilitySummary({
  agentRuntimes,
  results
}: {
  agentRuntimes: AgentRuntime[]
  results: ModelProfileAgentProbeResult[]
}) {
  const [dialogOpen, setDialogOpen] = useState(false)
  const items = results.map((result) => ({
    agent: getAgentIdentity(result, agentRuntimes),
    result
  }))

  return (
    <>
      <button
        aria-haspopup="dialog"
        aria-label={`查看 ${items.length} 个 Agent 的兼容性测试结果`}
        className={styles.compatibilitySummary}
        type="button"
        onClick={() => setDialogOpen(true)}
      >
        查看 {items.length} 个 Agent
      </button>
      {dialogOpen ? (
        <Suspense fallback={null}>
          <AgentCompatibilityDetailsModal items={items} onCancel={() => setDialogOpen(false)} />
        </Suspense>
      ) : null}
    </>
  )
}
