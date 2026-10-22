import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import PrerequisiteNotice from '.'

describe('PrerequisiteNotice', () => {
  it('renders one clear recovery action', async () => {
    const onAction = vi.fn()
    const user = userEvent.setup()

    render(
      <PrerequisiteNotice
        actionLabel="前往环境管理"
        description="当前运行环境尚未配置完整。"
        title="暂不能开始构建"
        onAction={onAction}
      />
    )

    expect(screen.getByRole('status')).toHaveTextContent('当前运行环境尚未配置完整。')
    await user.click(screen.getByRole('button', { name: '前往环境管理' }))
    expect(onAction).toHaveBeenCalledOnce()
  })
})
