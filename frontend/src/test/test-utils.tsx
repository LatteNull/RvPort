import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'

import type { ProjectEnvironment } from '@/types/project'

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  })
}

export function renderWithQueryClient(ui: ReactElement, queryClient = createTestQueryClient()) {
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }

  return { queryClient, ...render(ui, { wrapper: Wrapper }) }
}

export function createEnvironment(overrides: Partial<ProjectEnvironment> = {}): ProjectEnvironment {
  return {
    id: 'env-1',
    name: 'x86-builder',
    role: 'SOURCE',
    architecture: 'x86_64',
    os: 'Ubuntu 24.04',
    host: '192.0.2.10',
    sshPort: 22,
    workdir: '/workspace',
    authType: 'KEY',
    basicInfo: {
      arch: 'x86_64',
      basicTools: {},
      checkedAt: '2026-07-13T08:00:00+08:00',
      kernelVersion: '6.8.0',
      osName: 'Ubuntu',
      osVersion: '24.04',
      packageManager: 'apt',
      permissions: {},
      remoteUser: 'root',
      snapshotId: 'snapshot-1',
      snapshotKind: 'BASIC_CHECK',
      toolVersions: {},
      workingDirectory: {}
    },
    credentialsConfigured: true,
    connectionStatus: 'SUCCESS',
    ...overrides,
    jumpHostEnvironmentId: overrides.jumpHostEnvironmentId ?? null
  }
}
