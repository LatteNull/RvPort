import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { ProjectRuntimeEnvironments } from '@/types/project'

import RuntimeEnvironmentCards from './index'

const environments: ProjectRuntimeEnvironments = {
  missing: [],
  projectId: 'project-1',
  ready: true,
  sourceEnvironment: {
    architecture: 'x86_64',
    connectionStatus: 'SUCCESS',
    enabled: true,
    configVersion: 1,
    id: 'source-1',
    name: 'x86 builder',
    role: 'SOURCE'
  },
  targetEnvironment: {
    architecture: 'riscv64',
    connectionStatus: 'SUCCESS',
    enabled: true,
    configVersion: 1,
    id: 'target-1',
    name: 'RISC-V target',
    role: 'TARGET'
  },
  updatedBy: null,
  updatedAt: null,
  version: 1
}

describe('RuntimeEnvironmentCards', () => {
  it('can render a lightweight identity-only overview', () => {
    render(<RuntimeEnvironmentCards environments={environments} showConnectionStatus={false} />)

    expect(screen.getByText('x86 builder')).toBeInTheDocument()
    expect(screen.getByText('RISC-V target')).toBeInTheDocument()
    expect(screen.queryByText('环境状态')).not.toBeInTheDocument()
    expect(screen.queryByText('连接成功')).not.toBeInTheDocument()
  })

  it('keeps connection status in the default mode', () => {
    render(<RuntimeEnvironmentCards environments={environments} />)

    expect(screen.getAllByText('环境状态')).toHaveLength(2)
    expect(screen.getAllByText('连接成功')).toHaveLength(2)
  })

  it('keeps source and target placeholders when the current environments are not configured', () => {
    render(<RuntimeEnvironmentCards showConnectionStatus={false} />)

    expect(screen.getByText('x86 源环境')).toBeInTheDocument()
    expect(screen.getByText('RISC-V 目标环境')).toBeInTheDocument()
    expect(screen.getAllByText('待配置')).toHaveLength(2)
    expect(screen.getAllByText('-')).toHaveLength(2)
  })
})
