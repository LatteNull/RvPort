import { describe, expect, it } from 'vitest'

import {
  getSourceDisplayName,
  isCurrentBuildReadinessRecord,
  isTerminalBuildReadinessStatus
} from './buildReadinessContext'

describe('build readiness state helpers', () => {
  it('uses the repository name or uploaded filename as the source display name', () => {
    expect(
      getSourceDisplayName({
        active: true,
        id: 'git-source',
        type: 'GIT',
        version: 'main@abc123',
        versionNote: '',
        updatedAt: '2026-09-03T00:00:00Z',
        repositoryUrl: 'https://github.com/ISCAS/RvPort.git'
      })
    ).toBe('RvPort')
    expect(
      getSourceDisplayName({
        active: true,
        id: 'archive-source',
        type: 'ARCHIVE',
        version: 'v1',
        versionNote: '',
        updatedAt: '2026-09-03T00:00:00Z',
        fileName: 'rvport-v1.tar.gz'
      })
    ).toBe('rvport-v1.tar.gz')
  })

  it('only treats a successful record from the active source and runtime configuration as current', () => {
    expect(
      isCurrentBuildReadinessRecord(
        {
          currentRuntimeEnvironment: true,
          environmentConfigVersion: 4,
          sourceRevisionId: 'source-1'
        },
        'source-1',
        4
      )
    ).toBe(true)

    expect(
      isCurrentBuildReadinessRecord(
        {
          currentRuntimeEnvironment: true,
          environmentConfigVersion: 3,
          sourceRevisionId: 'source-1'
        },
        'source-1',
        4
      )
    ).toBe(false)
  })

  it('recognizes terminal task statuses without treating queued work as terminal', () => {
    expect(isTerminalBuildReadinessStatus('SUCCEEDED')).toBe(true)
    expect(isTerminalBuildReadinessStatus('FAILED')).toBe(true)
    expect(isTerminalBuildReadinessStatus('RUNNING')).toBe(false)
    expect(isTerminalBuildReadinessStatus('QUEUED')).toBe(false)
  })
})
