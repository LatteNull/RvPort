import { describe, expect, it } from 'vitest'

import { toEnvironmentInput, toEnvironmentUpdateRequest } from './environment-input'

describe('environment input mapping', () => {
  it('trims password environment fields and preserves password credentials', () => {
    expect(
      toEnvironmentInput({
        architecture: 'x86_64',
        authType: 'PASSWORD',
        host: ' 192.0.2.10 ',
        name: ' builder ',
        password: 'secret',
        role: 'SOURCE',
        sshPort: 22,
        username: 'root',
        workdir: ' /workspace '
      })
    ).toMatchObject({
      host: '192.0.2.10',
      name: 'builder',
      password: 'secret',
      username: 'root',
      workdir: '/workspace'
    })
  })

  it('omits the immutable name from an update request', () => {
    expect(
      toEnvironmentUpdateRequest({
        architecture: 'riscv64',
        authType: 'KEY',
        host: '192.0.2.20',
        name: 'target',
        privateKey: 'key',
        role: 'TARGET',
        sshPort: 2222,
        workdir: '/opt/target'
      })
    ).not.toHaveProperty('name')
  })

  it('preserves the required username for key-based authentication', () => {
    expect(
      toEnvironmentInput({
        architecture: 'riscv64',
        authType: 'KEY',
        host: '192.0.2.20',
        name: 'target',
        privateKey: 'key',
        role: 'TARGET',
        sshPort: 22,
        username: ' deploy ',
        workdir: '/opt/target'
      })
    ).toMatchObject({ username: 'deploy' })
  })
})
