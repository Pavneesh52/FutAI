import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { EvidenceViewer } from './EvidenceViewer'
import type { EvidenceItem } from '../api/client'

const mockEvidence: EvidenceItem[] = [
  {
    ref: 'team_match_stats:1:101',
    label: 'Arsenal xG',
    value: 1.84,
  },
  {
    ref: 'team_match_stats:2:101',
    label: 'Chelsea xG',
    value: 1.12,
  },
]

describe('EvidenceViewer', () => {
  it('renders nothing if evidence array is empty', () => {
    const { container } = render(<EvidenceViewer evidence={[]} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders collapsible evidence button and expands on click', () => {
    render(<EvidenceViewer evidence={mockEvidence} />)

    expect(screen.getByText('Deterministic Evidence')).toBeInTheDocument()
    expect(screen.getByText('2 sources')).toBeInTheDocument()

    // Initially collapsed
    expect(screen.queryByText('Arsenal xG')).not.toBeInTheDocument()

    // Click to expand
    fireEvent.click(screen.getByRole('button'))

    expect(screen.getByText('Arsenal xG')).toBeInTheDocument()
    expect(screen.getByText('1.84')).toBeInTheDocument()
    expect(screen.getByText('Chelsea xG')).toBeInTheDocument()
    expect(screen.getByText('1.12')).toBeInTheDocument()
    expect(screen.getByText('team_match_stats:1:101')).toBeInTheDocument()
  })
})
