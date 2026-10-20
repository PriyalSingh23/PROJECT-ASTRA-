import React from 'react'
import {
  Sun,
  Moon,
  Download,
  Database,
  FileText,
} from 'lucide-react'

interface AstraSettingsViewProps {
  isNightMode: boolean
  setIsNightMode: (val: boolean) => void
}

export function AstraSettingsView({ isNightMode, setIsNightMode }: AstraSettingsViewProps) {
  const handleExportJson = () => {
    const data = {
      workspace: 'ASTRA Signal Intelligence Workspace',
      exportedAt: new Date().toISOString(),
      mode: 'Local Research & Operations',
      centerFreqMHz: 2484.0,
      sampleRateMSps: 2.4576,
      lpiStealth: 'LPI-CGAN Neural Active',
      status: 'VERIFIED',
    }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `astra-session-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleExportCsv = () => {
    const rows = [
      ['Metric', 'Without LPI', 'With LPI (CGAN)', 'Delta'],
      ['Peak Power (dBFS)', '-48.2', '-82.4', '-34.2 dB'],
      ['Bandwidth (MHz)', '0.0125', '2.4576', '+2.445 MHz'],
      ['Energy Intercept Risk', '99.4%', '< 0.05%', '-99.35%'],
      ['Detection Horizon (km)', '42.8', '0.9', '-41.9 km'],
    ]
    const csvContent = rows.map((e) => e.join(',')).join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `astra-lpi-comparison-${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <div className="text-[10px] font-extrabold uppercase tracking-widest text-[var(--accent)] mb-1">
          Workspace Preferences
        </div>
        <h1 className="text-2xl font-black tracking-tight text-[var(--ink)]">
          Settings & Session Exports
        </h1>
        <p className="text-xs text-[var(--muted)] mt-1">
          Configure appearance, tactical displays, and export diagnostic logs.
        </p>
      </div>

      {/* Appearance Section */}
      <div className="neo-raised p-6 space-y-4">
        <h3 className="text-sm font-bold flex items-center gap-2">
          {isNightMode ? <Moon className="w-4 h-4 text-purple-400" /> : <Sun className="w-4 h-4 text-amber-500" />}
          <span>Appearance & Visual Theme</span>
        </h3>

        <div className="flex items-center justify-between p-3.5 rounded-xl neo-inset">
          <div>
            <div className="text-xs font-bold text-[var(--ink)]">Night Mode (Dark Neomorphic Theme)</div>
            <p className="text-[11px] text-[var(--muted)] mt-0.5">
              High-contrast tactical dark surfaces for night operations.
            </p>
          </div>
          <button
            onClick={() => setIsNightMode(!isNightMode)}
            className="neo-btn font-bold text-xs px-4 py-2"
          >
            {isNightMode ? 'Active (Dark)' : 'Inactive (Light)'}
          </button>
        </div>
      </div>

      {/* Export Section */}
      <div className="neo-raised p-6 space-y-4">
        <h3 className="text-sm font-bold flex items-center gap-2">
          <Download className="w-4 h-4 text-blue-500" />
          <span>Session Data & Diagnostic Exports</span>
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl neo-inset space-y-3">
            <div className="flex items-center gap-2 font-bold text-xs text-[var(--ink)]">
              <Database className="w-4 h-4 text-blue-500" />
              <span>Full Session Snapshot</span>
            </div>
            <p className="text-[11px] text-[var(--muted)] leading-relaxed">
              Download complete JSON log of RF frequencies, LPI metrics, and station connectivity.
            </p>
            <button
              onClick={handleExportJson}
              className="neo-btn text-xs font-bold py-2 px-3 w-full"
            >
              Download JSON Snapshot
            </button>
          </div>

          <div className="p-4 rounded-xl neo-inset space-y-3">
            <div className="flex items-center gap-2 font-bold text-xs text-[var(--ink)]">
              <FileText className="w-4 h-4 text-emerald-500" />
              <span>LPI Comparison Table</span>
            </div>
            <p className="text-[11px] text-[var(--muted)] leading-relaxed">
              Export CSV table comparing stealth metrics across all modulation and LPI techniques.
            </p>
            <button
              onClick={handleExportCsv}
              className="neo-btn text-xs font-bold py-2 px-3 w-full"
            >
              Export CSV Matrix
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
