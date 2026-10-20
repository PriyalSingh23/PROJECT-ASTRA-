import React, { useCallback, useEffect, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Gauge,
  HelpCircle,
  RefreshCw,
  Waves,
  XCircle,
} from 'lucide-react'
import { api } from '../services/api'
import { WaveformClass, WaveformComparison, WaveformTrack } from '../types'
import {
  ChartFrame,
  ConstellationChart,
  IQLegend,
  SpectrumChart,
  TimeDomainChart,
} from './waveform/WaveformCharts'

/**
 * Waveform Lab — the covert waveform next to a conventional one.
 *
 * This page exists to make one claim falsifiable in public: that the LPI-CGAN
 * waveform is harder to tell apart from noise than a normal data burst carrying
 * the same payload in the same bandwidth. Both columns are measured by the same
 * eight-domain battery, live, from the same code the gate uses.
 */

const CLASS_STYLE: Record<WaveformClass, { text: string; border: string; bg: string; label: string }> = {
  INDISTINGUISHABLE_FROM_NOISE: {
    text: 'text-emerald-300',
    border: 'border-emerald-800/60',
    bg: 'bg-emerald-950/40',
    label: 'indistinguishable from noise',
  },
  PARTIALLY_MASKED: {
    text: 'text-amber-300',
    border: 'border-amber-800/60',
    bg: 'bg-amber-950/40',
    label: 'partially masked',
  },
  DETECTABLE: {
    text: 'text-rose-300',
    border: 'border-rose-800/60',
    bg: 'bg-rose-950/40',
    label: 'detectable',
  },
  UNAVAILABLE: {
    text: 'text-zinc-400',
    border: 'border-zinc-700',
    bg: 'bg-zinc-900/60',
    label: 'not measured',
  },
}

function fmt(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  if (Math.abs(value) >= 1e5 || (Math.abs(value) > 0 && Math.abs(value) < 1e-3)) {
    return value.toExponential(2)
  }
  return value.toFixed(digits)
}

const PassMark: React.FC<{ passed: boolean }> = ({ passed }) =>
  passed ? (
    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
  ) : (
    <XCircle className="w-3.5 h-3.5 text-rose-400" />
  )

// ---------------------------------------------------------------------------
// One track column
// ---------------------------------------------------------------------------
const TrackColumn: React.FC<{ track: WaveformTrack; accent: string }> = ({ track, accent }) => {
  const cls = CLASS_STYLE[track.classification]
  const score = track.stealth_score

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 overflow-hidden">
      <header className="px-3 py-2.5 border-b border-zinc-800 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-sm" style={{ backgroundColor: accent }} />
            <h3 className="text-sm font-semibold text-zinc-100">{track.label}</h3>
          </div>
          <p className="text-[10px] font-mono text-zinc-500 mt-0.5 truncate" title={track.source}>
            {track.source}
          </p>
        </div>
        <span className={`shrink-0 inline-flex items-center px-2 py-0.5 rounded border text-[10px] font-mono font-semibold ${cls.border} ${cls.bg} ${cls.text}`}>
          {cls.label}
        </span>
      </header>

      <div className="p-3 space-y-3">
        {!track.available ? (
          <div className="text-[11px] font-mono text-amber-300/90 bg-amber-950/20 border border-amber-900/50 rounded px-2 py-2">
            These statistics could not be measured in this process.
            {track.unavailable_reason ? <div className="text-zinc-400 mt-1">{track.unavailable_reason}</div> : null}
          </div>
        ) : null}

        {/* Score row */}
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded border border-zinc-800 bg-zinc-950/60 px-2 py-1.5">
            <div className="text-[9px] font-mono uppercase tracking-wider text-zinc-500">EW gate</div>
            <div className="text-sm font-mono tabular-nums text-zinc-100">
              {track.available ? `${track.n_pass}/${track.n_domains}` : '—'}
            </div>
          </div>
          <div className="rounded border border-zinc-800 bg-zinc-950/60 px-2 py-1.5">
            <div className="text-[9px] font-mono uppercase tracking-wider text-zinc-500">Stealth score</div>
            <div className="text-sm font-mono tabular-nums text-zinc-100">
              {score === null || score === undefined ? '—' : score.toFixed(3)}
            </div>
          </div>
          <div className="rounded border border-zinc-800 bg-zinc-950/60 px-2 py-1.5">
            <div className="text-[9px] font-mono uppercase tracking-wider text-zinc-500">Sc deviation</div>
            <div className="text-sm font-mono tabular-nums text-zinc-100">{fmt(track.Sc, 3)}</div>
          </div>
        </div>

        {track.spec && (
          <p className="text-[10px] font-mono text-zinc-500 leading-relaxed">{track.spec}</p>
        )}

        <ChartFrame
          title="Time domain · frame 0"
          hint={`${track.frame_shape ? track.frame_shape[1] * track.frame_shape[2] : '—'} real samples`}
        >
          <TimeDomainChart points={track.waveform} />
          <div className="flex justify-end px-1 pt-1">
            <IQLegend />
          </div>
        </ChartFrame>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <ChartFrame
            title="Constellation"
            hint={track.symbol_centers.length ? 'cloud + symbol rate' : 'sample cloud'}
          >
            <ConstellationChart
              cloud={track.constellation}
              centers={track.symbol_centers}
              cloudColor={accent}
            />
          </ChartFrame>

          <ChartFrame title="PSD" hint="peak-normalised">
            <SpectrumChart points={track.spectrum} color={accent} />
          </ChartFrame>
        </div>

        {/* Domain table */}
        <div className="rounded-lg border border-zinc-800 overflow-hidden">
          <table className="w-full text-[11px] font-mono">
            <thead>
              <tr className="bg-zinc-950/80 text-zinc-500">
                <th className="text-left font-medium px-2 py-1.5 uppercase tracking-wider text-[9px]">Domain</th>
                <th className="text-right font-medium px-2 py-1.5 uppercase tracking-wider text-[9px]">Value</th>
                <th className="text-left font-medium px-2 py-1.5 uppercase tracking-wider text-[9px]">Gate</th>
                <th className="text-center font-medium px-2 py-1.5 uppercase tracking-wider text-[9px]">P/F</th>
              </tr>
            </thead>
            <tbody>
              {track.domains.map((dom) => (
                <tr key={dom.key} className="border-t border-zinc-800/70">
                  <td className="px-2 py-1 text-zinc-300">{dom.label}</td>
                  <td className="px-2 py-1 text-right tabular-nums text-zinc-100">
                    {fmt(dom.value, dom.key === 'ks' ? 4 : 4)}
                    {dom.unit && dom.unit !== '—' ? <span className="text-zinc-600 ml-1">{dom.unit}</span> : null}
                  </td>
                  <td className="px-2 py-1 text-zinc-500">{dom.criterion}</td>
                  <td className="px-2 py-1">
                    <div className="flex justify-center">
                      <PassMark passed={dom.passed} />
                    </div>
                  </td>
                </tr>
              ))}
              {!track.domains.length && (
                <tr>
                  <td colSpan={4} className="px-2 py-3 text-center text-zinc-600">
                    no measurements
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// View
// ---------------------------------------------------------------------------
export const WaveformLabView: React.FC = () => {
  const [data, setData] = useState<WaveformComparison | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [frames, setFrames] = useState<number>(4)
  const [showExplainer, setShowExplainer] = useState<boolean>(false)

  const load = useCallback(async (n: number) => {
    setLoading(true)
    try {
      const res = await api.getWaveformComparison(n)
      setData(res)
      setError(null)
    } catch (err: any) {
      setError(err?.message || 'Waveform comparison endpoint unreachable')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load(frames)
  }, [load, frames])

  const lpi = data?.tracks.lpi
  const conv = data?.tracks.conventional
  const flips = data?.contrast.filter((c) => c.flips) ?? []

  return (
    <div className="space-y-4">
      {/* Page header */}
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-3 border-b border-zinc-800 pb-3">
        <div>
          <div className="flex items-center gap-2">
            <Waves className="w-5 h-5 text-emerald-400" />
            <h1 className="text-lg font-semibold text-zinc-100 tracking-tight">Waveform Lab</h1>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-400">
              LPI-CGAN vs. conventional
            </span>
          </div>
          <p className="text-[11px] text-zinc-500 mt-1 max-w-2xl leading-relaxed">
            The covert waveform and a plain data burst, side by side, carrying the same payload in the same
            bandwidth and scored by the same eight-domain electronic-warfare battery.
          </p>
        </div>

        <div className="flex items-center gap-2 text-[11px] font-mono">
          <label className="flex items-center gap-1.5 text-zinc-500">
            frames
            <select
              value={frames}
              onChange={(e) => setFrames(Number(e.target.value))}
              className="bg-zinc-900 border border-zinc-700 rounded px-1.5 py-1 text-zinc-200 tabular-nums focus:outline-none focus:border-emerald-700"
            >
              {[2, 4, 8, 16].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <button
            onClick={() => load(frames)}
            className="flex items-center gap-1.5 px-2 py-1 rounded border border-zinc-700 text-zinc-300 hover:border-emerald-700 hover:text-emerald-300 transition-colors"
            title="Re-run the comparison"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            re-measure
          </button>
          {data && (
            <span
              className={`px-1.5 py-1 rounded border ${
                data.provenance === 'LIVE_COMPUTED'
                  ? 'border-emerald-800/60 text-emerald-300 bg-emerald-950/40'
                  : 'border-zinc-700 text-zinc-400 bg-zinc-900'
              }`}
              title={
                data.provenance === 'LIVE_COMPUTED'
                  ? 'Both tracks measured live from the trained generator and the baseline reference'
                  : 'The LPI generator could not be evaluated in this process; only the conventional reference was measured'
              }
            >
              {data.provenance === 'LIVE_COMPUTED' ? 'LIVE' : 'PARTIAL'}
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 text-[11px] font-mono text-rose-300 bg-rose-950/30 border border-rose-900/50 rounded-lg px-3 py-2">
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Verdict */}
      {data && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 space-y-3">
          <div className="flex items-start gap-3">
            <Gauge className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
            <div className="space-y-1 min-w-0">
              <p className="text-sm text-zinc-100 font-medium leading-snug">{data.verdict.headline}</p>
              <p className="text-[10px] font-mono text-zinc-500">{data.comparison_basis}</p>
              {(data.provenance === 'PARTIAL' || !data.tracks.lpi.available) && (
                <p className="text-[11px] font-mono text-amber-400">
                  (Analytical Fallback Active: Neural Inference Disabled)
                </p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
            <Stat label="LPI domains passed" value={data.verdict.lpi_pass === null ? '—' : `${data.verdict.lpi_pass}/8`} tone="good" />
            <Stat label="Conventional passed" value={`${data.verdict.conventional_pass}/8`} tone="bad" />
            <Stat label="Domains flipped" value={`${data.verdict.domains_flipped}`} tone="neutral" />
            <Stat
              label="Observation window"
              value={`${frames} × ${data.frame.frame_len} sa`}
              tone="neutral"
            />
          </div>

          {flips.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">Detector domains that separate them</span>
              {flips.map((f) => (
                <span
                  key={f.key}
                  className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-amber-800/50 bg-amber-950/30 text-amber-300"
                  title={`${f.label}: LPI ${fmt(f.lpi)} vs conventional ${fmt(f.conventional)} — ${f.criterion}`}
                >
                  {f.label}
                </span>
              ))}
            </div>
          )}

          <button
            onClick={() => setShowExplainer((s) => !s)}
            className="text-[10px] font-mono text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            {showExplainer ? '▾' : '▸'} How to read this
          </button>
          {showExplainer && (
            <div className="text-[11px] font-sans text-zinc-400 leading-relaxed space-y-2 border-l-2 border-zinc-800 pl-3">
              <p>
                Both columns carry <span className="text-zinc-200 font-mono">{data.frame.n_bits} information bits</span> per
                frame in <span className="text-zinc-200 font-mono">{data.frame.out_len} real samples</span> at{' '}
                <span className="text-zinc-200 font-mono">{(data.frame.fs_hz / 1000).toFixed(0)} kS/s</span>. The conventional
                burst is QPSK on a root-raised-cosine pulse at a matched symbol rate, so it gets no bandwidth advantage — if it
                scores worse, that is the shaping, not the payload.
              </p>
              <p>
                Each of the eight domains is a reference detector: KS tests the samples against a Gaussian, kurtosis checks the
                tails, spectral entropy and PAPR check flatness and envelope, circularity, SCF, the fourth-order cumulant and the
                Wigner–Ville ratio cover the higher-order and time–frequency structure. A <span className="text-emerald-300">PASS</span>{' '}
                means that detector cannot separate this waveform from noise on that domain.
              </p>
              <p className="text-zinc-500">{data.disclaimer}</p>
            </div>
          )}
        </div>
      )}

      {/* Tracks */}
      {loading && !data && (
        <div className="text-[11px] font-mono text-zinc-500 py-8 text-center">
          Synthesising both waveforms and running the eight-domain battery…
        </div>
      )}

      {data && lpi && conv && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <TrackColumn track={lpi} accent="#34d399" />
          <TrackColumn track={conv} accent="#fbbf24" />
        </div>
      )}

      {/* Contrast table */}
      {data && data.contrast.length > 0 && (
        <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 overflow-hidden">
          <header className="px-3 py-2 border-b border-zinc-800 flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300 font-mono">
              Head-to-head · same battery
            </h3>
            <span className="text-[10px] font-mono text-zinc-500">
              {data.contrast.filter((c) => c.flips).length} of {data.contrast.length} domains flip
            </span>
          </header>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px] font-mono">
              <thead>
                <tr className="bg-zinc-950/80 text-zinc-500">
                  <th className="text-left font-medium px-3 py-1.5 uppercase tracking-wider text-[9px]">Domain</th>
                  <th className="text-right font-medium px-3 py-1.5 uppercase tracking-wider text-[9px]">LPI-CGAN</th>
                  <th className="text-right font-medium px-3 py-1.5 uppercase tracking-wider text-[9px]">Conventional</th>
                  <th className="text-left font-medium px-3 py-1.5 uppercase tracking-wider text-[9px]">Gate</th>
                  <th className="text-center font-medium px-3 py-1.5 uppercase tracking-wider text-[9px]">Flip</th>
                </tr>
              </thead>
              <tbody>
                {data.contrast.map((row) => (
                  <tr key={row.key} className={`border-t border-zinc-800/70 ${row.flips ? 'bg-amber-950/10' : ''}`}>
                    <td className="px-3 py-1.5 text-zinc-300">{row.label}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">
                      <span className={row.lpi_pass ? 'text-emerald-300' : 'text-rose-300'}>{fmt(row.lpi)}</span>
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums">
                      <span className={row.conventional_pass ? 'text-emerald-300' : 'text-rose-300'}>
                        {fmt(row.conventional)}
                      </span>
                    </td>
                    <td className="px-3 py-1.5 text-zinc-500">{row.criterion}</td>
                    <td className="px-3 py-1.5 text-center">
                      {row.flips ? (
                        <span className="inline-flex items-center gap-1 text-amber-300">
                          <HelpCircle className="w-3 h-3" /> yes
                        </span>
                      ) : (
                        <span className="text-zinc-600">no</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {data && (
        <p className="text-[10px] font-mono text-zinc-600">
          generated {data.generated_at} · checkpoint {data.frame.n_bits}-bit frames · processing gain{' '}
          {data.frame.processing_gain_db} dB · DMR payload ceiling 280 B
        </p>
      )}
    </div>
  )
}

const Stat: React.FC<{ label: string; value: string; tone: 'good' | 'bad' | 'neutral' }> = ({ label, value, tone }) => {
  const color =
    tone === 'good' ? 'text-emerald-300' : tone === 'bad' ? 'text-rose-300' : 'text-zinc-200'
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2">
      <div className="text-[9px] font-mono uppercase tracking-wider text-zinc-500">{label}</div>
      <div className={`text-base font-mono tabular-nums ${color}`}>{value}</div>
    </div>
  )
}

export default WaveformLabView
