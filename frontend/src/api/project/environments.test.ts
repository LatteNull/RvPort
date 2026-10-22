import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  toEnvironmentConnectionRequest,
  toEnvironmentUpdateRequest
} from '@/pages/project-detail/StageDrawer/Environment/environment-input'
import { createEnvironmentFormValues } from '@/pages/project-detail/StageDrawer/Environment/model'
import { createEnvironment } from '@/test/test-utils'

const request = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn() }))
vi.mock('../request', () => ({ default: request }))
import {
  getProjectEnvironments,
  testProjectEnvironmentConnection,
  updateProjectEnvironment
} from './environments'

const fixture = {
  id: 'env-1',
  name: 'saved',
  role: 'SOURCE_X86',
  arch: 'x86_64',
  host: 'saved-host',
  sshPort: 22,
  username: 'saved-user',
  credential: { id: 'credential-1', configured: true, kind: 'SSH_PASSWORD' },
  status: 'AVAILABLE',
  basicInfo: null,
  enabled: true,
  workingDirectory: '/saved',
  jumpHost: null
}

describe('environment credential contract', () => {
  beforeEach(() => {
    request.post.mockResolvedValue({})
    request.patch.mockResolvedValue(fixture)
  })

  it.each(['SSH_PASSWORD', 'SSH_KEY'])(
    'maps username and credential id and retains %s without secrets',
    async (kind) => {
      request.get.mockResolvedValue({
        items: [{ ...fixture, credential: { ...fixture.credential, kind } }],
        total: 1
      })
      const page = await getProjectEnvironments('project', { page: 1, pageSize: 20 })
      const environment = page.items[0]
      expect(environment).toMatchObject({ username: 'saved-user', credentialId: 'credential-1' })
      const values = {
        ...createEnvironmentFormValues(environment),
        host: ' draft-host ',
        sshPort: 2222,
        username: ' draft-user ',
        workdir: '/draft',
        password: 'stale secret',
        privateKey: 'stale key'
      }
      await testProjectEnvironmentConnection(
        'project',
        toEnvironmentConnectionRequest(values, environment)
      )
      const payload = request.post.mock.calls[0][1]
      expect(payload).toMatchObject({
        host: 'draft-host',
        sshPort: 2222,
        username: 'draft-user',
        workingDirectory: '/draft',
        credentialId: 'credential-1'
      })
      for (const field of ['loginType', 'password', 'privateKey'])
        expect(payload).not.toHaveProperty(field)
      await updateProjectEnvironment(environment.id, toEnvironmentUpdateRequest(values))
      const update = request.patch.mock.calls[0][1]
      for (const field of ['loginType', 'password', 'privateKey'])
        expect(update).not.toHaveProperty(field)
    }
  )

  it.each(['PASSWORD', 'KEY'] as const)(
    'uses replacement %s instead of an old reference',
    async (authType) => {
      const environment = createEnvironment({ credentialId: 'old' })
      const values = {
        ...createEnvironmentFormValues(environment),
        credentialMode: 'replace' as const,
        authType,
        password: 'new-password',
        privateKey: 'new-key'
      }
      await testProjectEnvironmentConnection(
        'project',
        toEnvironmentConnectionRequest(values, environment)
      )
      const payload = request.post.mock.calls[0][1]
      expect(payload.loginType).toBe(authType)
      expect(payload).not.toHaveProperty('credentialId')
      expect(payload).toHaveProperty(
        authType === 'PASSWORD' ? 'password' : 'privateKey',
        authType === 'PASSWORD' ? 'new-password' : 'new-key'
      )
      expect(payload).not.toHaveProperty(authType === 'PASSWORD' ? 'privateKey' : 'password')
    }
  )

  it('permits normal updates without a credential reference but refuses retained precheck', () => {
    const environment = createEnvironment({ credentialId: null })
    const values = createEnvironmentFormValues(environment)
    expect(() => toEnvironmentConnectionRequest(values, environment)).toThrow('缺少引用')
    expect(toEnvironmentUpdateRequest(values)).not.toHaveProperty('authType')
  })
})
