import { MemoryRouter, useLocation } from 'react-router'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import NotFoundPage from '.'

describe('not found page', () => {
  it('returns to the home route', async () => {
    const user = userEvent.setup()

    function LocationDisplay() {
      return <output data-testid="location">{useLocation().pathname}</output>
    }

    render(
      <MemoryRouter initialEntries={['/missing-page']}>
        <NotFoundPage />
        <LocationDisplay />
      </MemoryRouter>
    )

    expect(screen.getByText('页面不存在')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '返回首页' }))
    expect(screen.getByTestId('location')).toHaveTextContent('/home')
  })
})
