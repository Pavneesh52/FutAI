import { useState, useMemo } from 'react'
import { Search, Calendar, Trophy, ChevronRight, Filter, Layers, BarChart2 } from 'lucide-react'
import type { MatchSummary } from '../api/client'

interface MatchListProps {
  matches: MatchSummary[]
  isLoading: boolean
  error?: Error | null
  onSelectMatch: (matchId: number) => void
  onRetry?: () => void
}

export function MatchList({ matches, isLoading, error, onSelectMatch, onRetry }: MatchListProps) {
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedCompetition, setSelectedCompetition] = useState<string>('all')

  const competitions = useMemo(() => {
    const set = new Set<string>()
    matches.forEach((m) => {
      if (m.competition) set.add(m.competition)
    })
    return ['all', ...Array.from(set)]
  }, [matches])

  const filteredMatches = useMemo(() => {
    return matches.filter((match) => {
      const home = match.home_team.name.toLowerCase()
      const away = match.away_team.name.toLowerCase()
      const comp = match.competition.toLowerCase()
      const season = match.season.toLowerCase()
      const query = searchTerm.toLowerCase()

      const matchesSearch =
        home.includes(query) ||
        away.includes(query) ||
        comp.includes(query) ||
        season.includes(query)

      const matchesComp = selectedCompetition === 'all' || match.competition === selectedCompetition

      return matchesSearch && matchesComp
    })
  }, [matches, searchTerm, selectedCompetition])

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-12 bg-slate-900/60 rounded-xl animate-pulse border border-slate-800/80" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-40 bg-slate-900/40 rounded-2xl animate-pulse border border-slate-800/60"
            />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-8 rounded-2xl border border-rose-900/50 bg-rose-950/20 text-center space-y-3">
        <p className="text-sm font-semibold text-rose-300">Failed to load matches</p>
        <p className="text-xs text-rose-400/80 max-w-md mx-auto">{error.message}</p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="px-4 py-2 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 border border-rose-500/30 text-xs font-medium transition-colors cursor-pointer"
          >
            Try Again
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Search & Filter Bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search teams (e.g. Arsenal, Chelsea), competitions, seasons..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 text-xs bg-slate-900/80 border border-slate-800 rounded-xl text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500/60 focus:ring-1 focus:ring-emerald-500/40 transition-all shadow-inner"
          />
          {searchTerm && (
            <button
              type="button"
              onClick={() => setSearchTerm('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-slate-200"
            >
              Clear
            </button>
          )}
        </div>

        {competitions.length > 2 && (
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            <Filter className="w-3.5 h-3.5 text-slate-400 shrink-0 ml-1" />
            {competitions.map((comp) => (
              <button
                key={comp}
                type="button"
                onClick={() => setSelectedCompetition(comp)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors cursor-pointer ${
                  selectedCompetition === comp
                    ? 'bg-emerald-500 text-slate-950 font-semibold shadow-sm'
                    : 'bg-slate-900/60 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 border border-slate-800'
                }`}
              >
                {comp === 'all' ? 'All Competitions' : comp}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Matches Grid */}
      {filteredMatches.length === 0 ? (
        <div className="p-12 text-center rounded-2xl border border-slate-800 bg-slate-900/30">
          <Layers className="w-8 h-8 mx-auto text-slate-500 mb-2" />
          <h4 className="text-sm font-semibold text-slate-300">No matches found</h4>
          <p className="text-xs text-slate-500 mt-1">
            {searchTerm
              ? `No matches match "${searchTerm}". Try a different search term.`
              : 'No matches ingested in the database yet.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredMatches.map((match) => {
            const hasScore =
              match.home_score !== null &&
              match.home_score !== undefined &&
              match.away_score !== null &&
              match.away_score !== undefined

            return (
              <div
                key={match.id}
                onClick={() => onSelectMatch(match.id)}
                className="group relative p-5 rounded-2xl border border-slate-800/80 bg-slate-900/50 hover:bg-slate-900/90 hover:border-emerald-500/50 transition-all duration-200 cursor-pointer shadow-lg hover:shadow-emerald-500/5 flex flex-col justify-between"
              >
                {/* Header row: competition & date */}
                <div className="flex items-center justify-between gap-2 text-[11px] text-slate-400 mb-4 pb-2.5 border-b border-slate-800/60">
                  <div className="flex items-center gap-1.5 truncate">
                    <Trophy className="w-3.5 h-3.5 text-amber-400/80 shrink-0" />
                    <span className="font-medium text-slate-300 truncate">{match.competition}</span>
                    <span className="text-slate-600">•</span>
                    <span className="text-slate-400">{match.season}</span>
                  </div>
                  <div className="flex items-center gap-1 shrink-0 text-slate-400">
                    <Calendar className="w-3 h-3" />
                    <span>{match.match_date}</span>
                  </div>
                </div>

                {/* Score / Teams Row */}
                <div className="my-1 flex items-center justify-between gap-4">
                  {/* Home Team */}
                  <div className="flex-1 text-left">
                    <p className="text-sm font-semibold text-slate-100 group-hover:text-emerald-300 transition-colors">
                      {match.home_team.name}
                    </p>
                    <p className="text-[10px] text-slate-500 font-mono">Home</p>
                  </div>

                  {/* Score */}
                  <div className="px-3 py-1.5 rounded-xl bg-slate-950/80 border border-slate-800 font-mono font-bold text-base text-slate-100 flex items-center gap-2 shadow-inner">
                    {hasScore ? (
                      <>
                        <span className="text-emerald-400">{match.home_score}</span>
                        <span className="text-slate-600">:</span>
                        <span className="text-emerald-400">{match.away_score}</span>
                      </>
                    ) : (
                      <span className="text-xs text-slate-400 font-normal">VS</span>
                    )}
                  </div>

                  {/* Away Team */}
                  <div className="flex-1 text-right">
                    <p className="text-sm font-semibold text-slate-100 group-hover:text-emerald-300 transition-colors">
                      {match.away_team.name}
                    </p>
                    <p className="text-[10px] text-slate-500 font-mono">Away</p>
                  </div>
                </div>

                {/* Footer action bar */}
                <div className="mt-4 pt-3 border-t border-slate-800/60 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 text-[10px] font-medium text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                      <BarChart2 className="w-3 h-3" /> Ready for AI Analysis
                    </span>
                  </div>
                  <span className="flex items-center gap-1 text-slate-400 group-hover:text-emerald-400 font-medium transition-colors">
                    View Match
                    <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
