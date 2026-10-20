import React from 'react'
import { Radio, ShieldAlert, Activity, Wifi, WifiOff, Terminal, Clock } from 'lucide-react'
import { QueueStats } from '../types'

interface HeaderProps {
  isBackendHealthy: boolean
  queueStats: QueueStats | null
  activeTab: 'console' | 'interop' | 'audit'
  setActiveTab: (tab: 'console' | 'interop' | 'audit') => void
}

export const Header: React.FC<HeaderProps> = ({
  isBackendHealthy,
  queueStats,
  activeTab,
  setActiveTab,
}) => {
  return (
    <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-40 px-4 py-3">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Branding */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shadow-sm">
            <Radio className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-bold text-lg tracking-wider text-slate-100 uppercase font-mono">
                SHADOWLINK <span className="text-emerald-400">FIELD</span>
              </h1>
              <span className="text-[10px] bg-slate-800 text-slate-300 font-mono px-1.5 py-0.5 rounded border border-slate-700">
                v2.0-STABLE
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Resilient Tactical Communications & Offline Messaging Platform
            </p>
          </div>
        </div>

        {/* Tactical Nav Tabs */}
        <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs font-medium">
          <button
            onClick={() => setActiveTab('console')}
            className={`px-3 py-1.5 rounded transition ${
              activeTab === 'console'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Tactical Outbox / Inbox
          </button>
          <button
            onClick={() => setActiveTab('interop')}
            className={`px-3 py-1.5 rounded transition ${
              activeTab === 'interop'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Interoperability (Motorola/Star-V/SDR)
          </button>
          <button
            onClick={() => setActiveTab('audit')}
            className={`px-3 py-1.5 rounded transition ${
              activeTab === 'audit'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Audit Log & Diagnostics
          </button>
        </div>

        {/* Status Indicators */}
        <div className="flex items-center gap-3">
          {/* Active Transport Pill */}
          <div className="flex items-center gap-1.5 bg-cyan-950/40 border border-cyan-800/60 px-2.5 py-1 rounded-md text-xs">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
            <span className="text-cyan-300 font-mono font-medium">TRANSPORT:</span>
            <span className="text-slate-200 font-bold font-mono">SIMULATION</span>
          </div>

          {/* Queue Count Pill */}
          <div className="flex items-center gap-1.5 bg-slate-800/80 border border-slate-700 px-2.5 py-1 rounded-md text-xs font-mono">
            <Clock className="w-3.5 h-3.5 text-amber-400" />
            <span className="text-slate-400">QUEUED:</span>
            <span className="text-amber-300 font-bold">{queueStats?.queued ?? 0}</span>
          </div>

          {/* Backend Status Pill */}
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono border ${
              isBackendHealthy
                ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-400'
                : 'bg-rose-950/40 border-rose-800/60 text-rose-400'
            }`}
          >
            {isBackendHealthy ? (
              <>
                <Wifi className="w-3.5 h-3.5" />
                <span>CORE: ONLINE</span>
              </>
            ) : (
              <>
                <WifiOff className="w-3.5 h-3.5" />
                <span>CORE: DISCONNECTED</span>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
