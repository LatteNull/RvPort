import { describe, expect, it } from 'vitest'

import type { ProjectTaskLogIncrementResponse } from '@/types/project/task-log'

import { appendTaskLogIncrement, createTaskLogStreamState } from './taskLogStream'

function increment(
  latestEventId: number,
  contents: { merged?: string; stderr?: string; stdout?: string } = {}
): ProjectTaskLogIncrementResponse {
  return {
    taskId: 'task-1',
    fromEventId: latestEventId,
    latestEventId,
    hasMore: false,
    logs: {
      merged: { content: contents.merged ?? '', returnedEvents: contents.merged ? 1 : 0 },
      stdout: { content: contents.stdout ?? '', returnedEvents: contents.stdout ? 1 : 0 },
      stderr: { content: contents.stderr ?? '', returnedEvents: contents.stderr ? 1 : 0 }
    }
  }
}

describe('task log stream state', () => {
  it('appends all log types and advances only to the response cursor', () => {
    const first = appendTaskLogIncrement(
      createTaskLogStreamState(),
      increment(4, { merged: '[STDOUT] first\n', stdout: 'first\n' })
    )
    const second = appendTaskLogIncrement(
      first,
      increment(9, { merged: '[STDERR] second\n', stderr: 'second\n' })
    )

    expect(second.cursor).toBe(9)
    expect(second.buffers.merged).toBe('[STDOUT] first\n[STDERR] second\n')
    expect(second.buffers.stdout).toBe('first\n')
    expect(second.buffers.stderr).toBe('second\n')
    expect(second.truncated).toBe(false)
  })

  it('preserves the requested cursor for an empty increment', () => {
    const state = appendTaskLogIncrement(createTaskLogStreamState(), {
      ...increment(37),
      fromEventId: null
    })

    expect(state.cursor).toBe(37)
    expect(state.buffers).toEqual({ merged: '', stdout: '', stderr: '' })
  })

  it('keeps the latest complete lines when the live display limit is exceeded', () => {
    const state = appendTaskLogIncrement(
      createTaskLogStreamState(),
      increment(3, {
        merged: 'one\ntwo\nthree\n',
        stdout: 'one\ntwo\nthree\n'
      }),
      { maxCharacters: 100, maxLines: 3 }
    )

    expect(state.buffers.stdout).toBe('two\nthree\n')
    expect(state.truncated).toBe(true)
  })
})
