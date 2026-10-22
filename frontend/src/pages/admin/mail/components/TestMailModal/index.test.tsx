import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '@/test/test-utils'

import TestMailModal from '.'

describe('test mail modal', () => {
  it('uses the native email input type and autocomplete hint', () => {
    renderWithQueryClient(
      <TestMailModal loading={false} visible onCancel={vi.fn()} onSubmit={vi.fn()} />
    )

    expect(screen.getByLabelText('收件人邮箱')).toHaveAttribute('type', 'email')
    expect(screen.getByLabelText('收件人邮箱')).toHaveAttribute('autocomplete', 'email')
  })
})
