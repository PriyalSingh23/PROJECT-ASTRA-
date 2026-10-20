import React, { useState } from 'react'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  RefreshCw,
} from 'lucide-react'
import { AnomalyDomain, AnomalyReport, AnomalyState, OperationalAnomaly } from '../../types'

export interface AnomalyStripProps {
  report: AnomalyReport | null
  loading?: boolean
  error?: string | null
  onRefresh?: () => void
  /** Tighter layout for embedding inside the 3D link view. */
  compact?: boolean
}

const STATE_STYLE: Record<AnomalyState, { dot: string; text: string; border: string; bg: string }> = {
  NOMINAL: { dot: 'bg-emerald-400', text: 'text-emerald-300', border: 'border-emerald-800/50', bg: 'bg-emerald-950/30' },
  WATCH: { dot: 'bg-amber-400', text: 'text-amber-300', border: 'border-amber-800/50', bg: 'bg-amber-950/30' },
  ANOMALY: { dot: 'bg-rose-500', text: 'text-rose-300', border: 'border-rose-800/50', bg: 'bg-rose-950/30' },
  UNKNOWN: { dot: 'bg-zinc-500', text: 'text-zinc-400', border: 'border-zinc-700/60', bg: 'bg-zinc-900/40' },
}

function fmt(value: number | null | undefined, digits: number = 4): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  if (Math.abs(value) >= 1e5 || (Math.abs(value) > 0 && Math.abs(value) < 1e-3)) {
    return value.toExponential(2)
  }
  return value.toFixed(digits)
}

const StateIcon: React.FC<{ state: AnomalyState }> = ({ state }) => {
  const cls = 'w-3 h-3'
  if (state === 'ANOMALY') return <AlertTriangle className={`${cls} text-rose-400`} />
  if (state === 'WATCH') return <AlertTriangle className={`${cls} text-amber-400`} />
  if (state === 'NOMINAL') return <CheckCircle2 className={`${cls} text-emerald-400`} />
  return <HelpCircle className={`${cls} text-zinc-500`} />
}

export const AnomalyStrip: React.FC<AnomalyStripProps> = ({
  report,
  loading,
  error,
  onRefresh,
  compact = false,
}) => {
  const [selectedKey, setSelectedKey] = useState<string | null>(null)

  const domains: AnomalyDomain[] = report?.domains ?? []
  const operational: OperationalAnomaly[] = report?.operational ?? []
  const all = [...domains, ...operational]
  const selected = all.find((item) => item.key === selectedKey) || null
  const summary = report?.summary

  const overall: AnomalyState = summary?.state ?? 'UNKNOWN'
  const style = STATE_STYLE[overall]

  return (
    <div className={`bg-zinc-900/60 border border-zinc-800 rounded-xl ${compact ? 'p-3' : 'p-4'} space-y-3`}>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div className="flex items-center space-x-2">
          <Activity className="w-4 h-4 text-emerald-400" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 font-mono">
            Integrity &amp; Anomaly Battery
          </h3>
          <span className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded border text-[10px] font-mono font-semibold ${style.border} ${style.bg} ${style.text}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${style.dot} ${overall !== 'NOMINAL' ? 'animate-pulse' : ''}`} />
            <span>{overall}</span>
          </span>
        </div>

        <div className="flex items-center space-x-3 text-[10px] font-mono text-zinc-500">
          {summary && (
            <span className="tabular-nums">
              {summary.counts.NOMINAL} nominal · {summary.counts.WATCH} watch · {summary.counts.ANOMALY} anomaly
              {summary.counts.UNKNOWN ? ` · ${summary.counts.UNKNOWN} unknown` : ''}
            </span>
          )}
          {report && (
            <span
              title={
                report.provenance === 'LIVE_COMPUTED'
                  ? 'Eight-domain battery measured from the loaded checkpoint'
                  : 'Checkpoint could not be evaluated in this process; showing the gated reference only'
              }
              className={`px-1.5 py-0.5 rounded border ${report.provenance === 'LIVE_COMPUTED'
                ? 'border-emerald-800/60 text-emerald-300 bg-emerald-950/40'
                : 'border-zinc-700 text-zinc-400 bg-zinc-900'}`}
            >
              {report.provenance === 'LIVE_COMPUTED' ? 'LIVE' : 'BASELINE REPLAY'}
            </span>
          )}
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="flex items-center space-x-1 text-zinc-400 hover:text-emerald-300 transition-colors"
              title="Re-measure now"
            >
              <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
              <span>re-measure</span>
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="text-[11px] font-mono text-rose-300 bg-rose-950/30 border border-rose-900/50 rounded px-2 py-1">
          {error}
        </div>
      )}

      {!report && loading && (
        <div className="text-[11px] font-mono text-zinc-500 py-2">
          Measuring eight EW domains and delivery-plane anomalies…
        </div>
      )}

      {report && (
        <>
          {/* The strip itself: one chip per measured domain / operational check. */}
          <div className="flex flex-wrap gap-1.5">
            {all.map((item) => {
              const isDomain = 'drift' in item
              const observed = item.observed
              const chip = STATE_STYLE[item.state]
              const active = item.key === selectedKey
              return (
                <button
                  key={item.key}
                  onClick={() => setSelectedKey(active ? null : item.key)}
                  title={isDomain
                    ? `${item.label}: observed ${fmt(observed)} ${item.unit} · baseline ${fmt(item.baseline)} ${item.unit}`
                    : `${item.label}: ${item.detail}`}
                  className={`group flex items-center space-x-1.5 px-2 py-1 rounded border transition-colors ${chip.border} ${chip.bg} ${
                    active ? 'ring-1 ring-zinc-500' : 'hover:border-zinc-600'
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${chip.dot}`} />
                  <span className="text-[10px] font-mono uppercase text-zinc-400 group-hover:text-zinc-300">
                    {item.label}
                  </span>
                  <span className={`text-[11px] font-mono tabular-nums font-semibold ${chip.text}`}>
                    {observed === null || observed === undefined ? '—' : fmt(observed, isDomain ? 4 : 1)}
                    {item.unit && item.unit !== '—' ? <span className="text-zinc-500 ml-0.5">{item.unit}</span> : null}
                  </span>
                </button>
              )
            })}
          </div>

          {/* Detail for the selected chip — baseline vs observed, openly. */}
          {selected && (
            <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-[11px] font-mono space-y-1">
              <div className="flex items-center space-x-2">
                <StateIcon state={selected.state} />
                <span className="text-zinc-200 font-semibold">{selected.label}</span>
                <span className="text-zinc-500">· {selected.state}</span>
              </div>
              {'drift' in selected ? (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                  <div>
                    <div className="text-zinc-500 text-[10px] uppercase">Baseline</div>
                    <div className="text-zinc-200 tabular-nums">{fmt(selected.baseline)} {selected.unit !== '—' ? selected.unit : ''}</div>
                  </div>
                  <div>
                    <div className="text-zinc-500 text-[10px] uppercase">Observed</div>
                    <div className="text-zinc-200 tabular-nums">{fmt(selected.observed)} {selected.unit !== '—' ? selected.unit : ''}</div>
                  </div>
                  <div>
                    <div className="text-zinc-500 text-[10px] uppercase">Drift vs tolerance</div>
                    <div className="text-zinc-200 tabular-nums">
                      {selected.drift === null ? '—' : fmt(selected.drift, 4)}
                      <span className="text-zinc-500"> / {selected.tolerance_mode === 'rel' ? 'rel ' : ''}{selected.tolerance}</span>
                    </div>
                  </div>
                  <div>
                    <div className="text-zinc-500 text-[10px] uppercase">Gate</div>
                    <div className={selected.passed ? 'text-emerald-300' : 'text-rose-300'}>
                      {selected.passed === null ? '—' : selected.passed ? 'PASS' : 'FAIL'}
                    </div>
                  </div>
                  <div className="col-span-2 sm:col-span-4 text-zinc-500 font-sans">
                    Expectation: {selected.expectation}. Drift is measured against the gated reference in{' '}
                    {report.baseline_source}.
                  </div>
                </div>
              ) : (
                <div className="text-zinc-400 font-sans">
                  {selected.detail}
                  {'threshold' in selected && selected.threshold && Object.keys(selected.threshold).length > 0 && (
                    <span className="text-zinc-500">
                      {' '}
                      (watch at {String(selected.threshold.watch_at)}, anomaly at {String(selected.threshold.anomaly_at)}; baseline {selected.baseline})
                    </span>
                  )}
                </div>
              )}
            </div>
          )}

          {report.ew.error && (
            <div className="text-[10px] font-mono text-amber-300/80">
              EW battery not measured this cycle: {report.ew.error}
            </div>
          )}
        </>
      )}
    </div>
  )
}
