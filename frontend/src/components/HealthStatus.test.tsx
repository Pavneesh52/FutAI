import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as client from '../api/client'
import { HealthStatus } from './HealthStatus'

vi.mock('../api/client', () => ({ fetchHealth: vi.fn() }))

const fetchHealth = vi.mocked(client.fetchHealth)

beforeEach(() => {
  fetchHealth.mockReset()
})

describe('HealthStatus', () => {
  it('renders "API healthy" when the API reports ok', async () => {
    fetchHealth.mockResolvedValue({ status: 'ok', db: 'ok' })

    render(<HealthStatus />)

    expect(await screen.findByText('API healthy')).toBeInTheDocument()
    expect(screen.getByText('Reachable')).toBeInTheDocument()
    expect(fetchHealth).toHaveBeenCalledWith(expect.any(AbortSignal))
  })

  it('renders a degraded notice when the database is unreachable', async () => {
    fetchHealth.mockResolvedValue({ status: 'degraded', db: 'unavailable' })

    render(<HealthStatus />)

    expect(await screen.findByText('API degraded')).toBeInTheDocument()
    expect(screen.getByText('Unreachable')).toBeInTheDocument()
  })

  it('renders an error card when the request fails, and can retry', async () => {
    fetchHealth.mockRejectedValueOnce(new Error('Failed to fetch'))

    render(<HealthStatus />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach the API')
    expect(screen.getByText('Failed to fetch')).toBeInTheDocument()

    fetchHealth.mockResolvedValueOnce({ status: 'ok', db: 'ok' })
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))

    expect(await screen.findByText('API healthy')).toBeInTheDocument()
    expect(fetchHealth).toHaveBeenCalledTimes(2)
  })
})
