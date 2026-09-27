import { useState } from 'react'
import { ChevronDown, ChevronUp, Database, ShieldCheck } from 'lucide-react'
import type { EvidenceItem } from '../api/client'

interface EvidenceViewerProps {
  evidence: EvidenceItem[]
}

export function EvidenceViewer({ evidence }: EvidenceViewerProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  if (!evidence || evidence.length === 0) {
    return null
  }

  const getRefBadgeColor = (ref: string) => {
    if (ref.startsWith('team_match_stats')) {
      return 'bg-blue-500/10 text-blue-400 border-blue-500/20'
    }
    if (ref.startsWith('player_match_stats')) {
      return 'bg-purple-500/10 text-purple-400 border-purple-500/20'
    }
    if (ref.startsWith('event')) {
      return 'bg-amber-500/10 text-amber-400 border-amber-500/20'
    }
    return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
  }

  return (
    <div className="mt-3 rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden transition-all duration-200">
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-left text-xs font-medium text-slate-300 hover:bg-slate-800/50 hover:text-white transition-colors cursor-pointer"
        aria-expanded={isExpanded}
      >
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>Deterministic Evidence</span>
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/25">
            {evidence.length} {evidence.length === 1 ? 'source' : 'sources'}
          </span>
        </div>
        <div className="flex items-center gap-1 text-slate-400 text-[11px]">
          <span>{isExpanded ? 'Hide sources' : 'View sources'}</span>
          {isExpanded ? (
            <ChevronUp className="w-3.5 h-3.5" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5" />
          )}
        </div>
      </button>

      {isExpanded && (
        <div className="p-3.5 pt-1 border-t border-slate-800/80 bg-slate-950/40 space-y-2">
          <p className="text-[11px] text-slate-400 pb-1">
            Every number in this analysis is grounded in the database tables below:
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {evidence.map((item, index) => (
              <div
                key={`${item.ref}-${index}`}
                className="flex flex-col justify-between p-2.5 rounded-lg bg-slate-900/90 border border-slate-800/80 hover:border-slate-700/80 transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-xs font-medium text-slate-200 line-clamp-1">
                    {item.label}
                  </span>
                  <span className="text-xs font-bold font-mono text-emerald-300 whitespace-nowrap">
                    {item.value !== null && item.value !== undefined ? String(item.value) : '—'}
                  </span>
                </div>
                <div className="mt-2 flex items-center gap-1.5 pt-1 border-t border-slate-800/60 text-[10px]">
                  <Database className="w-3 h-3 text-slate-500 shrink-0" />
                  <span
                    className={`font-mono px-1.5 py-0.5 rounded border text-[10px] truncate max-w-full ${getRefBadgeColor(
                      item.ref,
                    )}`}
                    title={item.ref}
                  >
                    {item.ref}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
