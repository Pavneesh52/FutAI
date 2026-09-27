import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { App } from './App'
import * as client from './api/client'

vi.mock('./api/client', () => ({
  fetchHealth: vi.fn(),
  fetchMatches: vi.fn(),
  fetchMatch: vi.fn(),
  fetchMatchStats: vi.fn(),
  fetchMatchEvents: vi.fn(),
  fetchMatchPlayers: vi.fn(),
  postAnalysis: vi.fn(),
}))

const mockFetchHealth = vi.mocked(client.fetchHealth)
const mockFetchMatches = vi.mocked(client.fetchMatches)
const mockFetchMatch = vi.mocked(client.fetchMatch)
const mockFetchMatchStats = vi.mocked(client.fetchMatchStats)

describe('App Smoke Integration', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mockFetchHealth.mockResolvedValue({ status: 'ok', db: 'ok' })
    mockFetchMatches.mockResolvedValue([
      {
        id: 101,
        home_team: { id: 1, name: 'Arsenal', country: 'England' },
        away_team: { id: 2, name: 'Chelsea', country: 'England' },
        competition: 'Premier League',
        season: '2023/2024',
        match_date: '2023-10-21',
        home_score: 2,
        away_score: 2,
      },
    ])
    mockFetchMatch.mockResolvedValue({
      id: 101,
      home_team: { id: 1, name: 'Arsenal', country: 'England' },
      away_team: { id: 2, name: 'Chelsea', country: 'England' },
      competition: 'Premier League',
      season: '2023/2024',
      match_date: '2023-10-21',
      home_score: 2,
      away_score: 2,
      event_count: 1420,
      has_stats: true,
    })
    mockFetchMatchStats.mockResolvedValue([
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
    ])
  })

  it('renders landing view, allows selecting match, and returning back', async () => {
    render(<App />)

    // Landing title
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/AI Football/i)

    // Wait for match card to render
    await waitFor(() => {
      expect(screen.getByText('Arsenal')).toBeInTheDocument()
      expect(screen.getByText('Chelsea')).toBeInTheDocument()
    })

    // Click on match to view details
    fireEvent.click(screen.getByText('Arsenal'))

    // Verify match details & comparison are rendered
    await waitFor(() => {
      expect(screen.getByText('Tactical Comparison Chart')).toBeInTheDocument()
      expect(screen.getByText('Football Analyst Agent')).toBeInTheDocument()
    })

    // Click "Back to Matches"
    fireEvent.click(screen.getByText('Back to Matches'))

    // Back on match list
    await waitFor(() => {
      expect(screen.getByText('Available Matches')).toBeInTheDocument()
    })
  })
})
