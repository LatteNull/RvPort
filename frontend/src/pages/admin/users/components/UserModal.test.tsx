import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '@/test/test-utils'

import UserModal from './UserModal'

describe('user modal', () => {
  it('exposes native account and email input semantics', () => {
    renderWithQueryClient(
      <UserModal loading={false} user={null} visible onCancel={vi.fn()} onSubmit={vi.fn()} />
    )

    expect(screen.getByLabelText('账号')).toHaveAttribute('autocomplete', 'username')
    expect(screen.getByLabelText('邮箱')).toHaveAttribute('type', 'email')
    expect(screen.getByLabelText('邮箱')).toHaveAttribute('autocomplete', 'email')
  })
})
