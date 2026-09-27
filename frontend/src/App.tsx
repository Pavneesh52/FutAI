import { useState } from 'react'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { Header } from './components/Header'
import { MatchList } from './components/MatchList'
import { MatchDetail } from './components/MatchDetail'
import { fetchMatches } from './api/client'
import { Sparkles, BarChart3, Bot, ShieldCheck } from 'lucide-react'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 2, // 2 minutes
      retry: 1,
    },
  },
})

function MainDashboard() {
  const [selectedMatchId, setSelectedMatchId] = useState<number | null>(null)

  const {
    data: matches = [],
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['matches'],
    queryFn: () => fetchMatches(),
  })

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-emerald-500/30 selection:text-emerald-200">
      <Header onHomeClick={() => setSelectedMatchId(null)} />

      <main className="flex-1 mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8 py-8 md:py-10">
        {selectedMatchId !== null ? (
          <MatchDetail matchId={selectedMatchId} onBack={() => setSelectedMatchId(null)} />
        ) : (
          <div className="space-y-10">
            {/* Hero Section */}
            <section className="relative overflow-hidden rounded-3xl border border-slate-800 bg-gradient-to-b from-slate-900/80 via-slate-900/40 to-slate-950 p-8 md:p-12 shadow-2xl">
              {/* Background Glows */}
              <div className="absolute -top-24 -left-24 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
              <div className="absolute -bottom-24 -right-24 w-96 h-96 bg-teal-500/10 rounded-full blur-3xl pointer-events-none" />

              <div className="relative z-10 max-w-3xl space-y-4">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold tracking-wider uppercase">
                  <Sparkles className="w-3.5 h-3.5" />
                  Grounded match analysis
                </div>

                <h1 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-white tracking-tight leading-tight">
                  AI Football <span className="text-emerald-400">Match Analyst</span>
                </h1>

                <p className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-2xl">
                  Pick a match, inspect tactical team comparisons (xG, PPDA, possession, shots), and
                  ask questions in natural language. Every single number in an answer traces
                  directly to deterministic tool calls and verified database metrics.
                </p>

                {/* Feature Pills */}
                <div className="pt-2 grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="flex items-center gap-2.5 p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs text-slate-300">
                    <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>Zero Invented Numbers</span>
                  </div>
                  <div className="flex items-center gap-2.5 p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs text-slate-300">
                    <BarChart3 className="w-4 h-4 text-teal-400 shrink-0" />
                    <span>Recharts Comparison</span>
                  </div>
                  <div className="flex items-center gap-2.5 p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs text-slate-300">
                    <Bot className="w-4 h-4 text-blue-400 shrink-0" />
                    <span>Deterministic Evidence Refs</span>
                  </div>
                </div>
              </div>
            </section>

            {/* Matches Section */}
            <section className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-bold text-white tracking-tight">Available Matches</h2>
                  <p className="text-xs text-slate-400">
                    Select any match to explore detailed statistics and converse with the analyst.
                  </p>
                </div>
                <div className="text-xs font-mono text-slate-400">
                  {matches.length} {matches.length === 1 ? 'match' : 'matches'} loaded
                </div>
              </div>

              <MatchList
                matches={matches}
                isLoading={isLoading}
                error={error as Error | null}
                onSelectMatch={(id) => setSelectedMatchId(id)}
                onRetry={() => refetch()}
              />
            </section>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 py-6 text-center text-xs text-slate-500">
        <div className="mx-auto max-w-7xl px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <p>© {new Date().getFullYear()} FutAI — Grounded Football Intelligence MVP</p>
          <p className="text-slate-600 font-mono text-[11px]">Phase 4 Thin UI • OpenAPI Driven</p>
        </div>
      </footer>
    </div>
  )
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <MainDashboard />
    </QueryClientProvider>
  )
}
