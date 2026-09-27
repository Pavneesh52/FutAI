import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ChatPanel } from './ChatPanel'
import * as client from '../api/client'

vi.mock('../api/client', () => ({
  postAnalysis: vi.fn(),
}))

const mockPostAnalysis = vi.mocked(client.postAnalysis)

describe('ChatPanel', () => {
  beforeEach(() => {
    mockPostAnalysis.mockReset()
  })

  it('renders suggested starter questions when conversation is empty', () => {
    render(<ChatPanel matchId={101} homeTeamName="Arsenal" awayTeamName="Chelsea" />)

    expect(screen.getByText(/Ask the AI Match Analyst/i)).toBeInTheDocument()
    expect(
      screen.getByText(/What was the final score and xG comparison between Arsenal and Chelsea\?/i),
    ).toBeInTheDocument()
  })

  it('submits a query and displays markdown answer with evidence refs', async () => {
    mockPostAnalysis.mockResolvedValueOnce({
      run_id: 'test-run-123',
      query_type: 'tactical',
      answer_markdown: 'Arsenal dominated with **1.84 xG** compared to Chelsea **1.12 xG**.',
      confidence: 0.95,
      degraded: false,
      retry_count: 0,
      evidence: [
        {
          ref: 'team_match_stats:1:101',
          label: 'Arsenal xG',
          value: 1.84,
        },
      ],
    })

    render(<ChatPanel matchId={101} homeTeamName="Arsenal" awayTeamName="Chelsea" />)

    const input = screen.getByPlaceholderText(/Ask about goals/i)
    fireEvent.change(input, { target: { value: 'Who had higher xG?' } })
    fireEvent.click(screen.getByTitle('Send query'))

    expect(mockPostAnalysis).toHaveBeenCalledWith({
      query: 'Who had higher xG?',
      match_id: 101,
    })

    await waitFor(() => {
      expect(screen.getByText(/Arsenal dominated with/i)).toBeInTheDocument()
    })

    expect(screen.getByText('tactical')).toBeInTheDocument()
    expect(screen.getByText('Confidence: 95%')).toBeInTheDocument()
    expect(screen.getByText('Deterministic Evidence')).toBeInTheDocument()
  })

  it('shows error banner when analysis call fails and allows retry', async () => {
    mockPostAnalysis.mockRejectedValueOnce(new Error('LLM timeout or model unreachable'))

    render(<ChatPanel matchId={101} homeTeamName="Arsenal" awayTeamName="Chelsea" />)

    const input = screen.getByPlaceholderText(/Ask about goals/i)
    fireEvent.change(input, { target: { value: 'Which team pressed more?' } })
    fireEvent.click(screen.getByTitle('Send query'))

    await waitFor(() => {
      expect(screen.getByText('Analysis Error')).toBeInTheDocument()
      expect(screen.getByText('LLM timeout or model unreachable')).toBeInTheDocument()
    })

    // Now mock success for retry
    mockPostAnalysis.mockResolvedValueOnce({
      run_id: 'retry-run-456',
      query_type: 'tactical',
      answer_markdown: 'Arsenal pressed with a PPDA of 8.4.',
      confidence: 1.0,
      degraded: false,
      retry_count: 0,
      evidence: [],
    })

    fireEvent.click(screen.getByText(/Retry query/i))

    await waitFor(() => {
      expect(screen.getByText('Arsenal pressed with a PPDA of 8.4.')).toBeInTheDocument()
    })
  })
})
