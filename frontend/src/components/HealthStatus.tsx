import { useEffect, useState } from 'react'

import { fetchHealth, type HealthResponse } from '../api/client'

type LoadState =
  | { kind: 'loading' }
  | { kind: 'loaded'; health: HealthResponse }
  | { kind: 'error'; message: string }

const DB_LABELS: Record<HealthResponse['db'], string> = {
  ok: 'Reachable',
  unavailable: 'Unreachable',
  not_configured: 'Not configured yet (Phase 1)',
}

/**
 * Calls `GET /health` on mount and renders the result, including the degraded case
 * where the API is serving but a dependency is down.
 */
export function HealthStatus() {
  const [state, setState] = useState<LoadState>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setState({ kind: 'loading' })

    fetchHealth(controller.signal)
      .then((health) => {
        setState({ kind: 'loaded', health })
      })
      .catch((error: unknown) => {
        // Cleanup aborts the request; that is not an error worth showing.
        if (controller.signal.aborted) return
        setState({
          kind: 'error',
          message: error instanceof Error ? error.message : 'Unknown error contacting the API',
        })
      })

    return () => {
      controller.abort()
    }
  }, [attempt])

  if (state.kind === 'loading') {
    return (
      <section className="rounded-lg border border-slate-800 bg-slate-900 p-6">
        <p role="status" className="text-slate-400">
          Checking API…
        </p>
      </section>
    )
  }

  if (state.kind === 'error') {
    return (
      <section className="rounded-lg border border-rose-900 bg-rose-950/40 p-6">
        <p role="alert" className="font-medium text-rose-300">
          Cannot reach the API
        </p>
        <p className="mt-1 text-sm text-rose-200/80">{state.message}</p>
        <p className="mt-1 text-sm text-rose-200/80">
          Is the backend running? <code>uvicorn app.main:app --reload</code>
        </p>
        <button
          type="button"
          onClick={() => setAttempt((previous) => previous + 1)}
          className="mt-4 rounded-md bg-rose-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-rose-400"
        >
          Retry
        </button>
      </section>
    )
  }

  const { status, db } = state.health
  const healthy = status === 'ok'

  return (
    <section
      className={
        healthy
          ? 'rounded-lg border border-emerald-900 bg-emerald-950/40 p-6'
          : 'rounded-lg border border-amber-900 bg-amber-950/40 p-6'
      }
    >
      <p
        role="status"
        className={healthy ? 'font-medium text-emerald-300' : 'font-medium text-amber-300'}
      >
        {healthy ? 'API healthy' : 'API degraded'}
      </p>

      <dl className="mt-4 grid grid-cols-[8rem_1fr] gap-y-1 text-sm">
        <dt className="text-slate-400">Status</dt>
        <dd className="text-slate-200">{status}</dd>
        <dt className="text-slate-400">Database</dt>
        <dd className="text-slate-200">{DB_LABELS[db]}</dd>
      </dl>

      {!healthy && (
        <p className="mt-4 text-sm text-amber-200/80">
          A dependency is unreachable, so the API is serving in a degraded state.
        </p>
      )}
    </section>
  )
}
