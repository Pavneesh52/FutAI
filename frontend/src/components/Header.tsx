import { useState } from 'react'
import { Activity, Sparkles, ChevronDown, ChevronUp } from 'lucide-react'
import { HealthStatus } from './HealthStatus'

interface HeaderProps {
  onHomeClick?: () => void
}

export function Header({ onHomeClick }: HeaderProps) {
  const [showHealthModal, setShowHealthModal] = useState(false)

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800 bg-slate-950/80 backdrop-blur-xl">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div onClick={onHomeClick} className="flex items-center gap-3 cursor-pointer group">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 p-0.5 shadow-lg shadow-emerald-500/20 group-hover:scale-105 transition-transform">
            <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-emerald-400" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-lg text-white tracking-tight">
                Fut<span className="text-emerald-400">AI</span>
              </span>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                MVP
              </span>
            </div>
            <p className="text-[10px] text-slate-400 -mt-0.5 hidden sm:block">
              Deterministic Grounded Football Analytics
            </p>
          </div>
        </div>

        {/* Right action: API Health Toggle */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setShowHealthModal(!showHealthModal)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-slate-800 bg-slate-900/80 hover:bg-slate-800 text-xs font-medium text-slate-300 hover:text-white transition-colors cursor-pointer shadow-sm"
            aria-expanded={showHealthModal}
          >
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <Activity className="w-3.5 h-3.5 text-slate-400" />
            <span className="hidden sm:inline">System Health</span>
            {showHealthModal ? (
              <ChevronUp className="w-3.5 h-3.5 text-slate-400" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            )}
          </button>
        </div>
      </div>

      {/* Expandable Health status drawer */}
      {showHealthModal && (
        <div className="border-t border-slate-800 bg-slate-900/95 backdrop-blur-md p-4 transition-all">
          <div className="mx-auto max-w-3xl">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Backend System Status
              </span>
              <button
                type="button"
                onClick={() => setShowHealthModal(false)}
                className="text-xs text-slate-400 hover:text-slate-200"
              >
                Close
              </button>
            </div>
            <HealthStatus />
          </div>
        </div>
      )}
    </header>
  )
}
