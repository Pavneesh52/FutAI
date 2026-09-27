import { useMemo } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'
import type { TeamMatchStats, TeamSummary } from '../api/client'
import { BarChart3, TableProperties, Info } from 'lucide-react'

interface TeamStatsComparisonProps {
  homeTeam: TeamSummary
  awayTeam: TeamSummary
  stats: TeamMatchStats[]
}

interface StatRowConfig {
  key: keyof TeamMatchStats
  label: string
  description?: string
  format?: (val: number | string | undefined | null) => string
  higherIsBetter?: boolean
}

export function TeamStatsComparison({ homeTeam, awayTeam, stats }: TeamStatsComparisonProps) {
  const { homeStats, awayStats } = useMemo(() => {
    if (!stats || stats.length === 0) {
      return { homeStats: undefined, awayStats: undefined }
    }
    const home = stats.find((s) => s.team_id === homeTeam.id) ?? stats[0]
    const away = stats.find((s) => s.team_id === awayTeam.id) ?? stats[1] ?? stats[0]
    return { homeStats: home, awayStats: away }
  }, [stats, homeTeam.id, awayTeam.id])

  // Chart data configuration
  const chartData = useMemo(() => {
    if (!homeStats || !awayStats) return []

    const hXg = homeStats.xg ?? 0
    const aXg = awayStats.xg ?? 0
    const hPoss = homeStats.possession_pct ?? 0
    const aPoss = awayStats.possession_pct ?? 0
    const hTilt = homeStats.field_tilt ?? 0
    const aTilt = awayStats.field_tilt ?? 0
    const hPpda = homeStats.ppda ?? 0
    const aPpda = awayStats.ppda ?? 0
    const hShots = homeStats.shots ?? 0
    const aShots = awayStats.shots ?? 0
    const hPasses = homeStats.passes ?? 0
    const aPasses = awayStats.passes ?? 0

    return [
      {
        metric: 'xG',
        [homeTeam.name]: Number(hXg.toFixed(2)),
        [awayTeam.name]: Number(aXg.toFixed(2)),
      },
      {
        metric: 'Possession %',
        [homeTeam.name]: Number(hPoss.toFixed(1)),
        [awayTeam.name]: Number(aPoss.toFixed(1)),
      },
      {
        metric: 'Field Tilt %',
        [homeTeam.name]: Number(hTilt.toFixed(1)),
        [awayTeam.name]: Number(aTilt.toFixed(1)),
      },
      {
        metric: 'PPDA (Pressing)',
        [homeTeam.name]: Number(hPpda.toFixed(1)),
        [awayTeam.name]: Number(aPpda.toFixed(1)),
      },
      {
        metric: 'Shots',
        [homeTeam.name]: hShots,
        [awayTeam.name]: aShots,
      },
      {
        metric: 'Passes / 10',
        [homeTeam.name]: Number((hPasses / 10).toFixed(1)),
        [awayTeam.name]: Number((aPasses / 10).toFixed(1)),
      },
    ]
  }, [homeStats, awayStats, homeTeam.name, awayTeam.name])

  const statRows: StatRowConfig[] = [
    {
      key: 'xg',
      label: 'Expected Goals (xG)',
      description: 'Quality of chances created',
      format: (val) => (typeof val === 'number' ? val.toFixed(2) : '—'),
      higherIsBetter: true,
    },
    {
      key: 'possession_pct',
      label: 'Possession',
      description: 'Percentage of time with ball in play',
      format: (val) => (typeof val === 'number' ? `${val.toFixed(1)}%` : '—'),
      higherIsBetter: true,
    },
    {
      key: 'field_tilt',
      label: 'Field Tilt',
      description: 'Share of final-third passes (territorial dominance)',
      format: (val) => (typeof val === 'number' ? `${val.toFixed(1)}%` : '—'),
      higherIsBetter: true,
    },
    {
      key: 'ppda',
      label: 'PPDA (Pressing Intensity)',
      description: 'Passes per Defensive Action (lower = more aggressive press)',
      format: (val) => (typeof val === 'number' ? val.toFixed(1) : '—'),
      higherIsBetter: false,
    },
    {
      key: 'shots',
      label: 'Total Shots',
      format: (val) => (val !== undefined && val !== null ? String(val) : '—'),
      higherIsBetter: true,
    },
    {
      key: 'shots_on_target',
      label: 'Shots on Target',
      format: (val) => (val !== undefined && val !== null ? String(val) : '—'),
      higherIsBetter: true,
    },
    {
      key: 'passes',
      label: 'Total Passes',
      format: (val) => (val !== undefined && val !== null ? String(val) : '—'),
      higherIsBetter: true,
    },
    {
      key: 'pass_accuracy',
      label: 'Pass Accuracy',
      format: (val) => (typeof val === 'number' ? `${val.toFixed(1)}%` : '—'),
      higherIsBetter: true,
    },
  ]

  if (!homeStats || !awayStats) {
    return (
      <div className="p-8 rounded-2xl border border-slate-800 bg-slate-900/40 text-center">
        <Info className="w-8 h-8 mx-auto text-slate-500 mb-2" />
        <h4 className="text-sm font-semibold text-slate-300">Team Statistics Not Yet Computed</h4>
        <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
          Detailed team match metrics have not been generated for this match yet.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Chart comparison card */}
      <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/50 backdrop-blur-sm shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400">
              <BarChart3 className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Tactical Comparison Chart</h3>
              <p className="text-[11px] text-slate-400">Key metrics side-by-side</p>
            </div>
          </div>
          <div className="flex items-center gap-4 text-xs font-medium">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded bg-emerald-500 inline-block shadow-sm"></span>
              <span className="text-slate-300">{homeTeam.name}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded bg-indigo-500 inline-block shadow-sm"></span>
              <span className="text-slate-300">{awayTeam.name}</span>
            </div>
          </div>
        </div>

        <div className="h-64 w-full pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
              <XAxis dataKey="metric" stroke="#64748b" fontSize={11} tickLine={false} />
              <YAxis stroke="#64748b" fontSize={11} tickLine={false} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  borderColor: '#334155',
                  borderRadius: '0.75rem',
                  color: '#f8fafc',
                  fontSize: '12px',
                  boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.5)',
                }}
                itemStyle={{ color: '#f8fafc' }}
                formatter={(value: any) => [value, '']}
              />
              <Legend wrapperStyle={{ display: 'none' }} />
              <Bar dataKey={homeTeam.name} fill="#10b981" radius={[4, 4, 0, 0]} maxBarSize={32} />
              <Bar dataKey={awayTeam.name} fill="#6366f1" radius={[4, 4, 0, 0]} maxBarSize={32} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Stat table comparison card */}
      <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/50 backdrop-blur-sm shadow-xl overflow-hidden">
        <div className="flex items-center gap-2 mb-4">
          <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400">
            <TableProperties className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Head-to-Head Statistics</h3>
            <p className="text-[11px] text-slate-400">
              Full metric breakdown with deterministic values
            </p>
          </div>
        </div>

        <div className="divide-y divide-slate-800/80">
          {statRows.map((row) => {
            const hVal = homeStats[row.key] as number | string | undefined | null
            const aVal = awayStats[row.key] as number | string | undefined | null

            const isNumeric = typeof hVal === 'number' && typeof aVal === 'number'
            const isHomeBetter =
              isNumeric && row.higherIsBetter !== undefined && hVal !== aVal
                ? row.higherIsBetter
                  ? (hVal as number) > (aVal as number)
                  : (hVal as number) < (aVal as number)
                : false
            const isAwayBetter =
              isNumeric && row.higherIsBetter !== undefined && hVal !== aVal
                ? row.higherIsBetter
                  ? (aVal as number) > (hVal as number)
                  : (aVal as number) < (hVal as number)
                : false

            // Compute relative ratio bar for visual comparison
            const hNum = typeof hVal === 'number' && hVal > 0 ? hVal : 0
            const aNum = typeof aVal === 'number' && aVal > 0 ? aVal : 0
            const total = hNum + aNum
            const homePercent = total > 0 ? Math.round((hNum / total) * 100) : 50

            return (
              <div key={row.key as string} className="py-3 px-1 flex flex-col gap-1.5">
                <div className="flex items-center justify-between text-xs">
                  <div
                    className={`font-mono font-semibold transition-colors ${
                      isHomeBetter ? 'text-emerald-400 font-bold' : 'text-slate-300'
                    }`}
                  >
                    {row.format ? row.format(hVal) : String(hVal ?? '—')}
                  </div>

                  <div className="text-center font-medium text-slate-200">
                    <span>{row.label}</span>
                    {row.description && (
                      <span className="block text-[10px] text-slate-400 font-normal">
                        {row.description}
                      </span>
                    )}
                  </div>

                  <div
                    className={`font-mono font-semibold transition-colors ${
                      isAwayBetter ? 'text-indigo-400 font-bold' : 'text-slate-300'
                    }`}
                  >
                    {row.format ? row.format(aVal) : String(aVal ?? '—')}
                  </div>
                </div>

                {/* Visual proportion bar */}
                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden flex">
                  <div
                    className="h-full bg-emerald-500 transition-all duration-300"
                    style={{ width: `${homePercent}%` }}
                  />
                  <div
                    className="h-full bg-indigo-500 transition-all duration-300"
                    style={{ width: `${100 - homePercent}%` }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
