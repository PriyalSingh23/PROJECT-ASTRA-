import React, { useState, useEffect } from 'react'
import {
  FileSpreadsheet,
  Download,
  CheckCircle2,
  AlertTriangle,
  Play,
  RotateCcw,
  Layers,
  LineChart as LineChartIcon,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts'
import { EvaluationReport } from '../../types'
import { api } from '../../services/api'

export const ExperimentCentreView: React.FC = () => {
  const [report, setReport] = useState<EvaluationReport | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [experimentId, setExperimentId] = useState<string>('EXP-ASTRA-2026-1019')
  const [notes, setNotes] = useState<string>('Baseline empirical link sweep across 0 to 10 dB SNR with Matched-Filter and Field BER.')

  useEffect(() => {
    api.getEvaluationReport().then((rep) => {
      setReport(rep)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const handleExportJSON = () => {
    if (!report) return
    const blob = new Blob([JSON.stringify({ experimentId, notes, report }, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${experimentId}.json`
    a.click()
  }

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-zinc-900/80 border border-zinc-800 p-4 rounded-xl flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2">
            <FileSpreadsheet className="w-5 h-5 text-emerald-400" />
            <h2 className="text-base font-bold font-mono text-zinc-100">
              Experiment &amp; Validation Centre
            </h2>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5 font-sans">
            Repeatable experiment snapshots, BER vs SNR evaluation sweeps, and empirical data export
          </p>
        </div>

        <button
          onClick={handleExportJSON}
          className="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 font-mono text-xs flex items-center space-x-2 transition-colors"
        >
          <Download className="w-4 h-4 text-emerald-400" />
          <span>Export Report (JSON)</span>
        </button>
      </div>

      {/* Experiment Configuration Snapshot */}
      <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3 font-mono text-xs">
        <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 flex items-center space-x-2">
          <span>Active Experiment Snapshot:</span>
          <span className="text-emerald-400">{experimentId}</span>
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-zinc-300">
          <div className="bg-zinc-950 p-2.5 rounded border border-zinc-850">
            <span className="text-zinc-500 block text-[10px]">Carrier Frequency</span>
            <span className="font-bold">2.484000 GHz</span>
            <span className="text-[9px] text-zinc-500 block">ISM Channel 14</span>
          </div>

          <div className="bg-zinc-950 p-2.5 rounded border border-zinc-850">
            <span className="text-zinc-500 block text-[10px]">Modulation</span>
            <span className="text-cyan-400 font-bold">LPI-CGAN Neural Spreading</span>
            <span className="text-[9px] text-zinc-500 block">576 Baseband Samples / Frame</span>
          </div>

          <div className="bg-zinc-950 p-2.5 rounded border border-zinc-850">
            <span className="text-zinc-500 block text-[10px]">Forward Error Correction</span>
            <span className="text-emerald-400 font-bold">Reed-Solomon RS(42, 34)</span>
            <span className="text-[9px] text-zinc-500 block">AES-256-GCM v2 Authenticated</span>
          </div>
        </div>
      </div>

      {/* BER vs SNR Plot */}
      {report && report.link_snrs && (
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 font-mono">
                Bit Error Rate (BER) &amp; Frame Error Rate (FER) vs SNR Sweep
              </h3>
              <p className="text-[11px] text-zinc-400 font-sans">
                Measured over 65,536 test bits per SNR evaluation point (0 to 10 dB)
              </p>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
              6 Sweep Points
            </span>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={report.link_snrs}>
                <defs>
                  <linearGradient id="expBerGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="snr_db" stroke="#71717a" fontSize={11} tickFormatter={(v) => `${v} dB`} />
                <YAxis stroke="#71717a" fontSize={11} tickFormatter={(v) => v.toExponential(1)} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', fontSize: '11px', fontFamily: 'monospace' }}
                />
                <Area type="monotone" dataKey="mf_ber" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#expBerGrad)" name="Matched-Filter BER" />
                <Area type="monotone" dataKey="field_ber" stroke="#38bdf8" strokeWidth={1.5} fillOpacity={0} name="Field BER" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Results Table */}
      {report && report.link_snrs && (
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3 font-mono text-xs">
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200">
            Empirical Test Run Data Table
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500 uppercase text-[10px]">
                  <th className="py-2">SNR (dB)</th>
                  <th className="py-2">Matched-Filter BER</th>
                  <th className="py-2">Field BER</th>
                  <th className="py-2">Frame Error Rate (FER)</th>
                  <th className="py-2">Bits Tested</th>
                  <th className="py-2">Frames Tested</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/40 text-zinc-300">
                {report.link_snrs.map((row) => (
                  <tr key={row.snr_db}>
                    <td className="py-2.5 font-bold text-emerald-400">{row.snr_db.toFixed(1)} dB</td>
                    <td className="py-2.5 text-zinc-200">{row.mf_ber.toExponential(3)}</td>
                    <td className="py-2.5 text-cyan-400">{row.field_ber.toExponential(3)}</td>
                    <td className="py-2.5 text-amber-400">{row.fer.toFixed(4)}</td>
                    <td className="py-2.5 text-zinc-400">{row.bits_tested.toLocaleString()}</td>
                    <td className="py-2.5 text-zinc-400">{row.frames_tested}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
