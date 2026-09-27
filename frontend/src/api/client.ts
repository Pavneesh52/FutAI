/**
 * Typed API client generated from the OpenAPI schema.
 */

import type { components } from '../types/api'

export type MatchSummary = components['schemas']['MatchSummary']
export type MatchDetail = components['schemas']['MatchDetail']
export type TeamSummary = components['schemas']['TeamSummary']
export type TeamMatchStats = components['schemas']['TeamMatchStats']
export type PlayerMatchStats = components['schemas']['PlayerMatchStats']
export type MatchEvent = components['schemas']['MatchEvent']
export type AnalysisRequest = components['schemas']['AnalysisRequest']
export type AnalysisResult = components['schemas']['AnalysisResult']
export type EvidenceItem = components['schemas']['EvidenceItem']
export type HealthResponse = components['schemas']['HealthResponse']

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    context?: Record<string, unknown>
    request_id?: string
  }
}

export class ApiError extends Error {
  readonly status: number | undefined
  readonly code: string
  readonly context?: Record<string, unknown>
  readonly requestId?: string

  constructor(
    message: string,
    status?: number,
    code = 'unknown_error',
    context?: Record<string, unknown>,
    requestId?: string,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.context = context
    this.requestId = requestId
  }
}

const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorData: ApiErrorBody | undefined
    try {
      errorData = (await response.json()) as ApiErrorBody
    } catch {
      // response was not JSON
    }

    if (errorData?.error) {
      throw new ApiError(
        errorData.error.message || `API responded with HTTP ${response.status}`,
        response.status,
        errorData.error.code,
        errorData.error.context,
        errorData.error.request_id,
      )
    }

    throw new ApiError(`API responded with HTTP ${response.status}`, response.status)
  }

  return (await response.json()) as T
}

/** Fetch API health status */
export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${API_URL}/health`, {
    signal,
    headers: { Accept: 'application/json' },
  })
  return handleResponse<HealthResponse>(response)
}

/** Fetch list of all ingested matches */
export async function fetchMatches(signal?: AbortSignal): Promise<MatchSummary[]> {
  const response = await fetch(`${API_URL}/matches`, {
    signal,
    headers: { Accept: 'application/json' },
  })
  return handleResponse<MatchSummary[]>(response)
}

/** Fetch one match by ID */
export async function fetchMatch(matchId: number, signal?: AbortSignal): Promise<MatchDetail> {
  const response = await fetch(`${API_URL}/matches/${matchId}`, {
    signal,
    headers: { Accept: 'application/json' },
  })
  return handleResponse<MatchDetail>(response)
}

/** Fetch team stats for a match */
export async function fetchMatchStats(
  matchId: number,
  teamId?: number,
  signal?: AbortSignal,
): Promise<TeamMatchStats[]> {
  const url = new URL(`${API_URL}/matches/${matchId}/stats`)
  if (teamId !== undefined) {
    url.searchParams.set('team_id', String(teamId))
  }
  const response = await fetch(url.toString(), {
    signal,
    headers: { Accept: 'application/json' },
  })
  return handleResponse<TeamMatchStats[]>(response)
}

/** Fetch events for a match */
export async function fetchMatchEvents(
  matchId: number,
  eventType?: string,
  signal?: AbortSignal,
): Promise<MatchEvent[]> {
  const url = new URL(`${API_URL}/matches/${matchId}/events`)
  if (eventType) {
    url.searchParams.set('event_type', eventType)
  }
  const response = await fetch(url.toString(), {
    signal,
    headers: { Accept: 'application/json' },
  })
  return handleResponse<MatchEvent[]>(response)
}

/** Fetch player aggregates for a match */
export async function fetchMatchPlayers(
  matchId: number,
  signal?: AbortSignal,
): Promise<PlayerMatchStats[]> {
  const response = await fetch(`${API_URL}/matches/${matchId}/players`, {
    signal,
    headers: { Accept: 'application/json' },
  })
  return handleResponse<PlayerMatchStats[]>(response)
}

/** Submit a natural language football question for grounded analysis */
export async function postAnalysis(
  request: AnalysisRequest,
  signal?: AbortSignal,
): Promise<AnalysisResult> {
  const response = await fetch(`${API_URL}/analysis`, {
    method: 'POST',
    signal,
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(request),
  })
  return handleResponse<AnalysisResult>(response)
}
