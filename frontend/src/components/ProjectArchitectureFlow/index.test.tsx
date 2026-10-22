import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import ProjectArchitectureFlow from '.'

describe('ProjectArchitectureFlow', () => {
  it('renders the shared architecture labels and direction', () => {
    render(<ProjectArchitectureFlow sourceArchitecture="x86_64" targetArchitecture="riscv64" />)

    expect(screen.getByLabelText('源架构 x86_64，目标架构 RISC-V')).toBeInTheDocument()
    expect(screen.getByText('x86_64')).toBeInTheDocument()
    expect(screen.getByText('RISC-V')).toBeInTheDocument()
  })
})
