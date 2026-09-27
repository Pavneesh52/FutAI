import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeft,
  Calendar,
  Trophy,
  Shield,
  Loader2,
  AlertTriangle,
  RotateCcw,
} from 'lucide-react'
import { fetchMatch, fetchMatchStats } from '../api/client'
import { TeamStatsComparison } from './TeamStatsComparison'
import { ChatPanel } from './ChatPanel'

interface MatchDetailProps {
  matchId: number
  onBack: () => void
}

export function MatchDetail({ matchId, onBack }: MatchDetailProps) {
  // Fetch match details
  const {
    data: match,
    isLoading: isLoadingMatch,
    error: matchError,
    refetch: refetchMatch,
  } = useQuery({
    queryKey: ['match', matchId],
    queryFn: () => fetchMatch(matchId),
  })

  // Fetch team stats
  const {
    data: stats,
    isLoading: isLoadingStats,
    error: statsError,
    refetch: refetchStats,
  } = useQuery({
    queryKey: ['match-stats', matchId],
    queryFn: () => fetchMatchStats(matchId),
  })

  if (isLoadingMatch) {
    return (
      <div className="py-20 flex flex-col items-center justify-center gap-3 text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
        <p className="text-sm font-medium">Loading match details and analytics...</p>
      </div>
    )
  }

  if (matchError || !match) {
    return (
      <div className="p-8 rounded-2xl border border-rose-900/50 bg-rose-950/20 text-center space-y-4">
        <AlertTriangle className="w-8 h-8 mx-auto text-rose-400" />
        <h3 className="text-base font-semibold text-rose-200">Failed to load match</h3>
        <p className="text-xs text-rose-300 max-w-md mx-auto">
          {(matchError as Error)?.message || 'Match not found or backend service unreachable.'}
        </p>
        <div className="flex items-center justify-center gap-3 pt-2">
          <button
            type="button"
            onClick={onBack}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors cursor-pointer"
          >
            Back to Match List
          </button>
          <button
            type="button"
            onClick={() => refetchMatch()}
            className="px-4 py-2 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 border border-rose-500/30 text-xs font-medium transition-colors cursor-pointer flex items-center gap-1.5"
          >
            <RotateCcw className="w-3.5 h-3.5" /> Try Again
          </button>
        </div>
      </div>
    )
  }

  const hasScore =
    match.home_score !== null &&
    match.home_score !== undefined &&
    match.away_score !== null &&
    match.away_score !== undefined

  return (
    <div className="space-y-6">
      {/* Back button & Breadcrumb */}
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/80 hover:bg-slate-800 border border-slate-800 text-xs font-medium text-slate-300 hover:text-white transition-all cursor-pointer shadow-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Matches</span>
        </button>

        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-slate-800/80 border border-slate-700/60 text-slate-300">
            <Trophy className="w-3 h-3 text-amber-400" />
            {match.competition}
          </span>
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-slate-800/80 border border-slate-700/60 text-slate-300">
            <Calendar className="w-3 h-3 text-slate-400" />
            {match.match_date}
          </span>
        </div>
      </div>

      {/* Match Header Hero Card */}
      <div className="relative overflow-hidden rounded-3xl border border-slate-800 bg-gradient-to-b from-slate-900/90 to-slate-950 p-6 md:p-8 shadow-2xl">
        {/* Glow accents */}
        <div className="absolute top-0 left-1/4 w-48 h-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 right-1/4 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row items-center justify-between gap-6">
          {/* Home Team */}
          <div className="flex-1 text-center md:text-left flex items-center md:items-start gap-4">
            <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0 shadow-lg">
              <Shield className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">
                Home Team
              </p>
              <h2 className="text-xl md:text-2xl font-bold text-white mt-0.5">
                {match.home_team.name}
              </h2>
              {match.home_team.country && (
                <p className="text-xs text-slate-400">{match.home_team.country}</p>
              )}
            </div>
          </div>

          {/* Scoreboard Center */}
          <div className="flex flex-col items-center justify-center px-6 py-3 rounded-2xl bg-slate-900/90 border border-slate-800/90 shadow-2xl">
            {hasScore ? (
              <div className="flex items-center gap-4 font-mono font-extrabold text-3xl md:text-4xl text-white tracking-tight">
                <span className="text-emerald-400">{match.home_score}</span>
                <span className="text-slate-600 font-normal">:</span>
                <span className="text-indigo-400">{match.away_score}</span>
              </div>
            ) : (
              <span className="text-base font-bold text-slate-400 uppercase tracking-widest">
                VS
              </span>
            )}
            <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wider mt-1">
              {match.season}
            </span>
          </div>

          {/* Away Team */}
          <div className="flex-1 text-center md:text-right flex flex-row-reverse items-center md:items-start gap-4">
            <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0 shadow-lg">
              <Shield className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs font-semibold text-indigo-400 uppercase tracking-wider">
                Away Team
              </p>
              <h2 className="text-xl md:text-2xl font-bold text-white mt-0.5">
                {match.away_team.name}
              </h2>
              {match.away_team.country && (
                <p className="text-xs text-slate-400">{match.away_team.country}</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid: Team Comparison + AI Chat Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Stats & Recharts Visual Comparison */}
        <div className="lg:col-span-6 space-y-6">
          {isLoadingStats ? (
            <div className="p-12 rounded-2xl border border-slate-800 bg-slate-900/40 text-center text-slate-400">
              <Loader2 className="w-6 h-6 animate-spin mx-auto text-emerald-400 mb-2" />
              <p className="text-xs">Loading team statistics comparison...</p>
            </div>
          ) : statsError ? (
            <div className="p-6 rounded-2xl border border-amber-900/40 bg-amber-950/20 text-center space-y-2">
              <p className="text-xs text-amber-300">Could not fetch team statistics.</p>
              <button
                type="button"
                onClick={() => refetchStats()}
                className="text-xs text-amber-400 underline hover:text-amber-300"
              >
                Retry
              </button>
            </div>
          ) : (
            <TeamStatsComparison
              homeTeam={match.home_team}
              awayTeam={match.away_team}
              stats={stats ?? []}
            />
          )}
        </div>

        {/* Right Column: Grounded LLM Chat Panel */}
        <div className="lg:col-span-6">
          <ChatPanel
            matchId={matchId}
            homeTeamName={match.home_team.name}
            awayTeamName={match.away_team.name}
          />
        </div>
      </div>
    </div>
  )
}
