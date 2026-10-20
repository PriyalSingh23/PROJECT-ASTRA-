import React from 'react'
import { CheckCircle2, Cpu, Fingerprint, HardDrive, ShieldCheck, XCircle, Zap } from 'lucide-react'
import { AnomalyReport } from '../../types'

export interface ModelHealthPanelProps {
  report: AnomalyReport | null
  loading?: boolean
}

function ber(value: number): string {
  if (!value) return '0'
  return value < 1e-3 ? value.toExponential(2) : value.toFixed(4)
}

/**
 * The honest model header: real checkpoint identity, real inference device,
 * real gated link performance. No metric on this panel is synthesised in the
 * browser — every value is served by the integrity endpoint.
 */
export const ModelHealthPanel: React.FC<ModelHealthPanelProps> = ({ report, loading }) => {
  if (!report) {
    return (
      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 text-[11px] font-mono text-zinc-500">
        {loading ? 'Reading checkpoint identity…' : 'Model telemetry unavailable.'}
      </div>
    )
  }

  const m = report.model
  const verified = m.manifest_verified

  return (
    <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div className="flex items-center space-x-2">
          <Cpu className="w-4 h-4 text-emerald-400" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 font-mono">
            LPI-CGAN Model Identity
          </h3>
          <span className="text-[10px] font-mono text-zinc-500">{m.subsystem}</span>
        </div>
        <span
          className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded border text-[10px] font-mono font-semibold ${
            verified
              ? 'border-emerald-800/60 bg-emerald-950/40 text-emerald-300'
              : 'border-rose-800/60 bg-rose-950/40 text-rose-300'
          }`}
        >
          {verified ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
          <span>{verified ? 'MANIFEST VERIFIED' : 'MANIFEST MISMATCH'}</span>
        </span>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 font-mono text-xs">
        <div className="bg-zinc-950 border border-zinc-850 rounded-lg p-3">
          <div className="flex items-center space-x-1 text-[10px] uppercase text-zinc-500">
            <Fingerprint className="w-3 h-3" />
            <span>Checkpoint SHA-256</span>
          </div>
          <div className="text-zinc-200 mt-1 truncate" title={m.sha256 || ''}>
            {m.sha256_short || 'n/a'}
          </div>
          <div className="text-[10px] text-zinc-500 mt-0.5">
            {m.checkpoint}
            {m.size_bytes ? ` · ${(m.size_bytes / 1024 / 1024).toFixed(2)} MB` : ''}
          </div>
        </div>

        <div className="bg-zinc-950 border border-zinc-850 rounded-lg p-3">
          <div className="flex items-center space-x-1 text-[10px] uppercase text-zinc-500">
            <HardDrive className="w-3 h-3" />
            <span>Training epoch</span>
          </div>
          <div className="text-zinc-200 mt-1 tabular-nums">{m.epoch ?? '—'}</div>
          <div className="text-[10px] text-zinc-500 mt-0.5 truncate" title={m.generation || ''}>
            {m.generation || m.exported_from || ''}
          </div>
        </div>

        <div className="bg-zinc-950 border border-zinc-850 rounded-lg p-3">
          <div className="flex items-center space-x-1 text-[10px] uppercase text-zinc-500">
            <Zap className="w-3 h-3" />
            <span>Inference device</span>
          </div>
          <div className="text-zinc-200 mt-1 uppercase">{m.inference_device}</div>
          <div className="text-[10px] text-zinc-500 mt-0.5">
            {m.mps_available ? `MPS available (${m.recommended_device})` : `torch ${m.pytorch_version}`}
          </div>
        </div>

        <div className="bg-zinc-950 border border-zinc-850 rounded-lg p-3">
          <div className="flex items-center space-x-1 text-[10px] uppercase text-zinc-500">
            <ShieldCheck className="w-3 h-3" />
            <span>Stealth gate</span>
          </div>
          <div className={`mt-1 tabular-nums ${m.n_pass && m.n_pass >= 7 ? 'text-emerald-300' : 'text-amber-300'}`}>
            {m.n_pass ?? '—'} / 8 pass
          </div>
          <div className="text-[10px] text-zinc-500 mt-0.5">
            Sc {m.stealth?.Sc !== undefined ? m.stealth.Sc.toFixed(4) : '—'} · adv {m.adversary_acc_pct !== null ? `${m.adversary_acc_pct.toFixed(1)}%` : '—'}
          </div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-[11px] font-mono">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-500 uppercase text-[10px]">
              <th className="py-1.5">SNR</th>
              <th className="py-1.5">Matched-filter BER</th>
              <th className="py-1.5">Field BER</th>
              <th className="py-1.5">Frame error rate</th>
              <th className="py-1.5">Bits tested</th>
              <th className="py-1.5">Frames</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/40 text-zinc-300">
            {m.link_snrs.length === 0 && (
              <tr>
                <td colSpan={6} className="py-2 text-zinc-500">
                  No link measurements in the evaluation report.
                </td>
              </tr>
            )}
            {m.link_snrs.map((row) => (
              <tr key={row.snr_db}>
                <td className="py-1.5 text-zinc-200 tabular-nums">{row.snr_db.toFixed(1)} dB</td>
                <td className="py-1.5 tabular-nums">{ber(row.mf_ber)}</td>
                <td className="py-1.5 tabular-nums text-emerald-300">{ber(row.field_ber)}</td>
                <td className="py-1.5 tabular-nums">{row.fer === 0 ? '0' : row.fer.toFixed(4)}</td>
                <td className="py-1.5 tabular-nums text-zinc-500">{row.bits_tested.toLocaleString()}</td>
                <td className="py-1.5 tabular-nums text-zinc-500">{row.frames_tested}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="text-[10px] font-mono text-zinc-500">
        Gate verdict: {m.gate_verdict || '—'} · baseline source: {report.baseline_source}
        {report.ew.n_frames ? ` · EW sample: ${report.ew.n_frames} frames` : ''}
      </div>
    </div>
  )
}
