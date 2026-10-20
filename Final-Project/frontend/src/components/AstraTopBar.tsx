import React, { useState, useEffect } from 'react'
import {
  Sun,
  Moon,
  RefreshCw,
  Bell,
  Radio,
  CheckCircle2,
} from 'lucide-react'
import { AstraTab } from './AstraSidebar'

interface AstraTopBarProps {
  activeTab: AstraTab
  isNightMode: boolean
  setIsNightMode: (val: boolean) => void
  isBackendHealthy: boolean
}

export function AstraTopBar({
  activeTab,
  isNightMode,
  setIsNightMode,
  isBackendHealthy,
}: AstraTopBarProps) {
  const [clock, setClock] = useState<string>('--:--:--')

  useEffect(() => {
    const updateTime = () => {
      const d = new Date()
      setClock(d.toLocaleTimeString([], { hour12: false }))
    }
    updateTime()
    const timer = setInterval(updateTime, 1000)
    return () => clearInterval(timer)
  }, [])

  const tabLabels: Record<AstraTab, string> = {
    overview: 'Overview',
    spectrum: 'Spectrum & Waterfall Lab',
    waveform: 'Waveform Analysis',
    topology: '3D Tactical Mesh',
    messages: 'Secure Messaging',
    research: 'Research & CGAN Studio',
    hardware: 'RF Hardware & SDR',
    settings: 'Settings & Export',
  }

  return (
    <header className="h-16 px-6 border-b border-[var(--line)] bg-[var(--bg)]/90 backdrop-blur-md sticky top-0 z-20 flex items-center justify-between gap-4 select-none">
      {/* Breadcrumb Path */}
      <div className="flex items-center gap-2 text-xs font-semibold text-[var(--muted)]">
        <span className="font-extrabold text-[var(--ink)]">ASTRA</span>
        <span className="text-[var(--subtle)]">›</span>
        <span className="text-[var(--accent)] font-bold">{tabLabels[activeTab]}</span>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-3">
        {/* System Status Indicator */}
        <div className="neo-inset px-3 py-1.5 rounded-xl flex items-center gap-2 text-[11px] font-bold text-[var(--muted)]">
          <span
            className={`w-2 h-2 rounded-full ${
              isBackendHealthy
                ? 'bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.6)]'
                : 'bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.6)]'
            }`}
          />
          <span className="hidden sm:inline">
            {isBackendHealthy ? 'Systems Nominal' : 'Reconnecting'}
          </span>
          <span className="text-[var(--subtle)] hidden sm:inline">·</span>
          <span className="font-mono text-[var(--ink)]">{clock}</span>
        </div>

        {/* Night Mode Switcher */}
        <button
          onClick={() => setIsNightMode(!isNightMode)}
          className="neo-btn p-2 rounded-xl text-[var(--ink)]"
          title={isNightMode ? 'Switch to Light Theme' : 'Switch to Night Theme'}
          aria-label="Toggle Night Mode"
        >
          {isNightMode ? (
            <Sun className="w-4 h-4 text-amber-400" />
          ) : (
            <Moon className="w-4 h-4 text-slate-600" />
          )}
        </button>

        {/* Refresh Button */}
        <button
          onClick={() => window.location.reload()}
          className="neo-btn p-2 rounded-xl text-[var(--muted)] hover:text-[var(--accent)]"
          title="Refresh Workspace"
          aria-label="Refresh Workspace"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>
    </header>
  )
}
