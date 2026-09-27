import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { MatchList } from './MatchList'
import type { MatchSummary } from '../api/client'

const mockMatches: MatchSummary[] = [
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
  {
    id: 102,
    home_team: { id: 3, name: 'Real Madrid', country: 'Spain' },
    away_team: { id: 4, name: 'Barcelona', country: 'Spain' },
    competition: 'La Liga',
    season: '2023/2024',
    match_date: '2023-10-28',
    home_score: 1,
    away_score: 2,
  },
]

describe('MatchList', () => {
  it('renders loading skeleton when loading', () => {
    const { container } = render(
      <MatchList matches={[]} isLoading={true} onSelectMatch={vi.fn()} />,
    )
    expect(container.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0)
  })

  it('renders error state and handles retry', () => {
    const onRetry = vi.fn()
    render(
      <MatchList
        matches={[]}
        isLoading={false}
        error={new Error('Failed to load')}
        onSelectMatch={vi.fn()}
        onRetry={onRetry}
      />,
    )
    expect(screen.getByText('Failed to load matches')).toBeInTheDocument()
    expect(screen.getByText('Failed to load')).toBeInTheDocument()

    fireEvent.click(screen.getByText('Try Again'))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('renders match list and filters by team search', () => {
    const onSelect = vi.fn()
    render(<MatchList matches={mockMatches} isLoading={false} onSelectMatch={onSelect} />)

    expect(screen.getByText('Arsenal')).toBeInTheDocument()
    expect(screen.getByText('Chelsea')).toBeInTheDocument()
    expect(screen.getByText('Real Madrid')).toBeInTheDocument()
    expect(screen.getByText('Barcelona')).toBeInTheDocument()

    // Filter by search query
    const searchInput = screen.getByPlaceholderText(/Search teams/i)
    fireEvent.change(searchInput, { target: { value: 'Arsenal' } })

    expect(screen.getByText('Arsenal')).toBeInTheDocument()
    expect(screen.queryByText('Real Madrid')).not.toBeInTheDocument()

    // Click on match card
    fireEvent.click(screen.getByText('Arsenal'))
    expect(onSelect).toHaveBeenCalledWith(101)
  })
})
