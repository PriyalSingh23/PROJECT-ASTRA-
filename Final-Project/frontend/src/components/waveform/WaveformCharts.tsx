import React from 'react'
import { ScatterPoint, SpectrumPoint, WaveformSample } from '../../types'

/**
 * Chart primitives for the Waveform Lab.
 *
 * Deliberately hand-rolled SVG rather than a charting library: three fixed
 * views (time domain, constellation, PSD) do not justify a dependency, and
 * `vectorEffect="non-scaling-stroke"` keeps the traces crisp at any width,
 * which a canvas-based library would not do for free.
 */

const AXIS = 'var(--line)'
const GRID = 'var(--grid)'
const LABEL = 'var(--muted)'

const Frame: React.FC<{
  title: string
  hint?: string
  children: React.ReactNode
}> = ({ title, hint, children }) => (
  <div className="rounded-xl border border-slate-200 dark:border-[var(--line)] bg-white dark:bg-[var(--surface)] neo-sm overflow-hidden shadow-xs">
    <div className="flex items-baseline justify-between px-3 py-2 border-b border-slate-200 dark:border-[var(--line)] bg-slate-50 dark:bg-[var(--surface-raised)]/60">
      <span className="text-[10px] font-bold uppercase tracking-widest text-slate-900 dark:text-[var(--ink)]">{title}</span>
      {hint && <span className="text-[10px] font-mono text-slate-500 dark:text-[var(--muted)] tabular-nums">{hint}</span>}
    </div>
    <div className="p-3 bg-white dark:bg-[#0B111A]">{children}</div>
  </div>
)

// ---------------------------------------------------------------------------
// Time domain — I and Q on a shared scale
// ---------------------------------------------------------------------------
export const TimeDomainChart: React.FC<{
  points: WaveformSample[]
  height?: number
}> = ({ points, height = 130 }) => {
  const W = 480
  const H = height
  const PAD = 14
  if (!points.length) {
    return <div className="text-[11px] font-mono text-zinc-600 py-6 text-center">no samples</div>
  }
  const values = points.flatMap((p) => [p.i, p.q])
  const extent = Math.max(0.5, ...values.map((v) => Math.abs(v))) * 1.1
  const x = (idx: number) => PAD + (idx / Math.max(1, points.length - 1)) * (W - 2 * PAD)
  const y = (v: number) => H / 2 - (v / extent) * (H / 2 - PAD)

  const path = (key: 'i' | 'q') =>
    points.map((p, idx) => `${idx === 0 ? 'M' : 'L'}${x(idx).toFixed(2)},${y(p[key]).toFixed(2)}`).join(' ')

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height }} role="img" aria-label="Time-domain I/Q waveform">
      <line x1={PAD} y1={H / 2} x2={W - PAD} y2={H / 2} stroke={AXIS} strokeWidth={1} />
      <line x1={PAD} y1={PAD} x2={PAD} y2={H - PAD} stroke={GRID} strokeWidth={1} />
      <path d={path('i')} fill="none" stroke="#34d399" strokeWidth={1.4} vectorEffect="non-scaling-stroke" />
      <path d={path('q')} fill="none" stroke="#38bdf8" strokeWidth={1.4} vectorEffect="non-scaling-stroke" opacity={0.9} />
      <text x={W - PAD} y={PAD - 3} textAnchor="end" fill={LABEL} fontSize={9} fontFamily="ui-monospace, monospace">
        ±{extent.toFixed(2)}
      </text>
      <text x={PAD + 4} y={H - 3} fill={LABEL} fontSize={9} fontFamily="ui-monospace, monospace">
        0 … {points.length - 1}
      </text>
    </svg>
  )
}

export const IQLegend: React.FC = () => (
  <div className="flex items-center gap-3 text-[10px] font-mono text-zinc-500">
    <span className="flex items-center gap-1">
      <span className="w-3 h-0.5 bg-emerald-400 inline-block" /> I
    </span>
    <span className="flex items-center gap-1">
      <span className="w-3 h-0.5 bg-sky-400 inline-block" /> Q
    </span>
  </div>
)

// ---------------------------------------------------------------------------
// Constellation — dense sample cloud, optional symbol-rate overlay
// ---------------------------------------------------------------------------
export const ConstellationChart: React.FC<{
  cloud: ScatterPoint[]
  centers?: ScatterPoint[]
  height?: number
  cloudColor?: string
}> = ({ cloud, centers = [], height = 200, cloudColor = '#34d399' }) => {
  const W = 260
  const H = height
  const PAD = 16
  const all = [...cloud, ...centers]
  if (!all.length) {
    return <div className="text-[11px] font-mono text-zinc-600 py-8 text-center">no samples</div>
  }
  const extent =
    Math.max(0.4, ...all.map((p) => Math.max(Math.abs(p.i), Math.abs(p.q)))) * 1.12
  const sx = (v: number) => W / 2 + (v / extent) * (W / 2 - PAD)
  const sy = (v: number) => H / 2 - (v / extent) * (H / 2 - PAD)
  const r = (extent / 24).toFixed(3)

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height }} role="img" aria-label="IQ constellation">
      {[0.5, 1.0].map((frac) => (
        <React.Fragment key={frac}>
          <circle cx={W / 2} cy={H / 2} r={(frac * (W / 2 - PAD)).toFixed(2)} fill="none" stroke={GRID} strokeWidth={1} />
        </React.Fragment>
      ))}
      <line x1={PAD} y1={H / 2} x2={W - PAD} y2={H / 2} stroke={AXIS} strokeWidth={1} />
      <line x1={W / 2} y1={PAD} x2={W / 2} y2={H - PAD} stroke={AXIS} strokeWidth={1} />
      {cloud.map((p, idx) => (
        <circle key={`c${idx}`} cx={sx(p.i).toFixed(2)} cy={sy(p.q).toFixed(2)} r={r} fill={cloudColor} opacity={0.55} />
      ))}
      {centers.map((p, idx) => (
        <circle
          key={`s${idx}`}
          cx={sx(p.i).toFixed(2)}
          cy={sy(p.q).toFixed(2)}
          r="2.6"
          fill="none"
          stroke="#fbbf24"
          strokeWidth={1}
          vectorEffect="non-scaling-stroke"
        />
      ))}
      <text x={W - 4} y={H / 2 - 4} textAnchor="end" fill={LABEL} fontSize={9} fontFamily="ui-monospace, monospace">
        {extent.toFixed(2)}
      </text>
      <text x={W / 2 + 4} y={H - 4} fill={LABEL} fontSize={9} fontFamily="ui-monospace, monospace">
        I
      </text>
      <text x={4} y={PAD + 8} fill={LABEL} fontSize={9} fontFamily="ui-monospace, monospace">
        Q
      </text>
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Power spectral density
// ---------------------------------------------------------------------------
export const SpectrumChart: React.FC<{
  points: SpectrumPoint[]
  height?: number
  color?: string
}> = ({ points, height = 150, color = '#34d399' }) => {
  const W = 480
  const H = height
  const PAD = 18
  if (!points.length) {
    return <div className="text-[11px] font-mono text-zinc-600 py-6 text-center">no spectrum</div>
  }
  const fMin = points[0].freq_khz
  const fMax = points[points.length - 1].freq_khz
  const pMin = Math.max(-60, Math.min(...points.map((p) => p.power_db)))
  const x = (f: number) => PAD + ((f - fMin) / Math.max(1e-9, fMax - fMin)) * (W - 2 * PAD)
  const y = (p: number) => H - PAD - ((p - pMin) / Math.max(1e-9, 0 - pMin)) * (H - 2 * PAD)
  const path = points.map((p, idx) => `${idx === 0 ? 'M' : 'L'}${x(p.freq_khz).toFixed(2)},${y(p.power_db).toFixed(2)}`).join(' ')

  const marks = [0, -10, -20, pMin]
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height }} role="img" aria-label="Power spectral density">
      {marks.map((m) => (
        <line key={m} x1={PAD} y1={y(m).toFixed(2)} x2={W - PAD} y2={y(m).toFixed(2)} stroke={GRID} strokeWidth={1} />
      ))}
      <line x1={W / 2} y1={PAD} x2={W / 2} y2={H - PAD} stroke={AXIS} strokeWidth={1} strokeDasharray="2 3" />
      <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} stroke={AXIS} strokeWidth={1} />
      <path d={path} fill="none" stroke={color} strokeWidth={1.3} vectorEffect="non-scaling-stroke" />
      {marks.map((m) => (
        <text key={`t${m}`} x={PAD - 3} y={y(m) + 3} textAnchor="end" fill={LABEL} fontSize={9} fontFamily="ui-monospace, monospace">
          {m.toFixed(0)}
        </text>
      ))}
      <text x={PAD} y={H - 5} fill={LABEL} fontSize={9} fontFamily="ui-monospace, monospace">
        {fMin.toFixed(0)} kHz
      </text>
      <text x={W - PAD} y={H - 5} textAnchor="end" fill={LABEL} fontSize={9} fontFamily="ui-monospace, monospace">
        +{fMax.toFixed(0)} kHz
      </text>
      <text x={W / 2} y={H - 5} textAnchor="middle" fill={LABEL} fontSize={9} fontFamily="ui-monospace, monospace">
        baseband
      </text>
    </svg>
  )
}

export { Frame as ChartFrame }
