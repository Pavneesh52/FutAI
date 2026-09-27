import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { TeamStatsComparison } from './TeamStatsComparison'
import type { TeamMatchStats, TeamSummary } from '../api/client'

const homeTeam: TeamSummary = { id: 1, name: 'Arsenal', country: 'England' }
const awayTeam: TeamSummary = { id: 2, name: 'Chelsea', country: 'England' }

const mockStats: TeamMatchStats[] = [
  {
    team_id: 1,
    match_id: 101,
    team_name: 'Arsenal',
    possession_pct: 58.2,
    xg: 1.84,
    ppda: 8.4,
    field_tilt: 64.1,
    shots: 14,
    shots_on_target: 6,
    passes: 512,
    pass_accuracy: 88.5,
    formation: '4-3-3',
  },
  {
    team_id: 2,
    match_id: 101,
    team_name: 'Chelsea',
    possession_pct: 41.8,
    xg: 1.12,
    ppda: 14.2,
    field_tilt: 35.9,
    shots: 8,
    shots_on_target: 3,
    passes: 360,
    pass_accuracy: 81.2,
    formation: '4-2-3-1',
  },
]

describe('TeamStatsComparison', () => {
  it('renders fallback notice when stats are missing or empty', () => {
    render(<TeamStatsComparison homeTeam={homeTeam} awayTeam={awayTeam} stats={[]} />)
    expect(screen.getByText('Team Statistics Not Yet Computed')).toBeInTheDocument()
  })

  it('renders tactical comparison chart header and head-to-head stat rows', () => {
    render(<TeamStatsComparison homeTeam={homeTeam} awayTeam={awayTeam} stats={mockStats} />)

    expect(screen.getByText('Tactical Comparison Chart')).toBeInTheDocument()
    expect(screen.getByText('Head-to-Head Statistics')).toBeInTheDocument()

    // Check stats are rendered
    expect(screen.getByText('1.84')).toBeInTheDocument()
    expect(screen.getByText('1.12')).toBeInTheDocument()
    expect(screen.getByText('58.2%')).toBeInTheDocument()
    expect(screen.getByText('41.8%')).toBeInTheDocument()
    expect(screen.getByText('8.4')).toBeInTheDocument()
    expect(screen.getByText('14.2')).toBeInTheDocument()
  })
})
