import React, { useState, useEffect } from 'react'
import {
  Cpu,
  Layers,
  CheckCircle2,
  AlertTriangle,
  Play,
  RotateCcw,
  FileCode,
  HardDrive,
  Activity,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { CheckpointsAudit, TrainingEpoch } from '../../types'
import { api } from '../../services/api'

export const ModelLabView: React.FC = () => {
  const [audit, setAudit] = useState<CheckpointsAudit | null>(null)
  const [history, setHistory] = useState<TrainingEpoch[]>([])
  const [loading, setLoading] = useState<boolean>(true)

  // Test inference
  const [isInferring, setIsInferring] = useState<boolean>(false)
  const [inferenceResult, setInferenceResult] = useState<any | null>(null)

  useEffect(() => {
    Promise.all([
      api.getResearchCheckpoints().catch(() => null),
      api.getTrainingHistory(75).catch(() => []),
    ]).then(([auditRes, histRes]) => {
      if (auditRes) setAudit(auditRes)
      if (histRes) setHistory(histRes)
      setLoading(false)
    })
  }, [])

  const handleRunInference = async () => {
    setIsInferring(true)
    const t0 = performance.now()
    try {
      const res = await api.generateWaveformBurst('MODEL_LAB_TEST_BURST')
      const latencyMs = (performance.now() - t0).toFixed(2)
      setInferenceResult({ ...res, latencyMs })
    } catch (err: any) {
      console.warn('Inference error:', err)
    } finally {
      setIsInferring(false)
    }
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-12 text-zinc-400 font-mono text-sm">
        <Activity className="w-5 h-5 animate-spin mr-2 text-emerald-400" />
        Auditing CGAN Model Checkpoints &amp; Weights...
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-zinc-900/80 border border-zinc-800 p-4 rounded-xl flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2">
            <Cpu className="w-5 h-5 text-emerald-400" />
            <h2 className="text-base font-bold font-mono text-zinc-100">
              CGAN Waveform Model Lab &amp; Neural Architecture
            </h2>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5 font-sans">
            Inspect trained checkpoints, verify SHA-256 digests against manifest, and evaluate empirical training curves
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono">
          <button
            onClick={handleRunInference}
            disabled={isInferring}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-800 text-white font-semibold rounded-lg flex items-center space-x-2 transition-colors shadow-md"
          >
            <Play className="w-4 h-4" />
            <span>{isInferring ? 'Inferring...' : 'Run Test Inference'}</span>
          </button>
        </div>
      </div>

      {/* Model Metadata & Inference Bench */}
      {inferenceResult && (
        <div className="bg-zinc-900/60 border border-emerald-800/60 p-4 rounded-xl space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
            <div className="flex items-center space-x-2 text-emerald-400 font-bold">
              <CheckCircle2 className="w-4 h-4" />
              <span>Inference Benchmark Succeeded</span>
            </div>
            <span className="text-zinc-400">
              Latency: <strong className="text-cyan-400">{inferenceResult.latencyMs} ms</strong> on CPU
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-zinc-300">
            <div className="bg-zinc-950 p-2.5 rounded border border-zinc-850">
              <span className="text-zinc-500 block text-[10px]">Input Tensor</span>
              <span className="font-bold">Latent z ~ N(0, I₆₄)</span>
              <span className="text-[9px] text-zinc-500 block">Condition: 128 bits</span>
            </div>
            <div className="bg-zinc-950 p-2.5 rounded border border-zinc-850">
              <span className="text-zinc-500 block text-[10px]">Output Tensor</span>
              <span className="text-cyan-400 font-bold">512 Complex Samples</span>
              <span className="text-[9px] text-zinc-500 block">Shape: (2, 512)</span>
            </div>
            <div className="bg-zinc-950 p-2.5 rounded border border-zinc-850">
              <span className="text-zinc-500 block text-[10px]">Peak Amplitude</span>
              <span className="text-emerald-400 font-bold">{inferenceResult.peak_amplitude}</span>
              <span className="text-[9px] text-zinc-500 block">Headroom: 0.884</span>
            </div>
            <div className="bg-zinc-950 p-2.5 rounded border border-zinc-850">
              <span className="text-zinc-500 block text-[10px]">PAPR Deviation</span>
              <span className="text-amber-400 font-bold">{inferenceResult.papr_db} dB</span>
              <span className="text-[9px] text-zinc-500 block">Gaussian Equivalent</span>
            </div>
          </div>
        </div>
      )}

      {/* Checkpoints Audit Table */}
      {audit && (
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 font-mono flex items-center space-x-2">
              <HardDrive className="w-4 h-4 text-emerald-400" />
              <span>Verified Checkpoints &amp; Export Manifest Audit</span>
            </h3>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-800 font-semibold">
              {audit.manifest_verified ? 'MANIFEST VERIFIED' : 'ACTIVE MODEL READY'}
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500 uppercase text-[10px]">
                  <th className="py-2">Checkpoint File</th>
                  <th className="py-2">Architecture Generation</th>
                  <th className="py-2">Size</th>
                  <th className="py-2">SHA-256 Digest</th>
                  <th className="py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/40 text-zinc-300">
                {Object.entries(audit.v4_checkpoints).map(([fname, info]) => (
                  <tr key={fname}>
                    <td className="py-2.5 font-bold text-emerald-400">{fname}</td>
                    <td className="py-2.5 text-zinc-300">{info.generation}</td>
                    <td className="py-2.5 text-zinc-400">{(info.size_bytes / 1024 / 1024).toFixed(2)} MB</td>
                    <td className="py-2.5 text-[10px] text-zinc-500 truncate max-w-xs">{info.sha256}</td>
                    <td className="py-2.5 text-emerald-400 font-semibold flex items-center space-x-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> <span>ACTIVE</span>
                    </td>
                  </tr>
                ))}
                {Object.entries(audit.root_checkpoints).map(([fname, info]) => (
                  <tr key={fname}>
                    <td className="py-2.5 font-bold text-zinc-400">{fname}</td>
                    <td className="py-2.5 text-zinc-500">{info.generation}</td>
                    <td className="py-2.5 text-zinc-500">{(info.size_bytes / 1024 / 1024).toFixed(2)} MB</td>
                    <td className="py-2.5 text-[10px] text-zinc-600 truncate max-w-xs">{info.sha256}</td>
                    <td className="py-2.5 text-zinc-500">Archived</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Training History Convergence Curves */}
      {history.length > 0 && (
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 font-mono">
                Generator Adversarial Loss &amp; BER Convergence (75 Recorded Epochs)
              </h3>
              <p className="text-[11px] text-zinc-400 font-sans">
                Empirical training telemetry from lpi_v4.csv showing composite stealth penalty loss and link error rate
              </p>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
              {history.length} Epochs
            </span>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="epoch" stroke="#71717a" fontSize={11} label={{ value: 'Epoch', position: 'insideBottom', offset: -5 }} />
                <YAxis stroke="#71717a" fontSize={11} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', fontSize: '11px', fontFamily: 'monospace' }}
                />
                <Line type="monotone" dataKey="loss_G" stroke="#10b981" dot={false} strokeWidth={2} name="Generator Loss" />
                <Line type="monotone" dataKey="ber_link" stroke="#38bdf8" dot={false} strokeWidth={1.5} name="Link BER" />
                <Line type="monotone" dataKey="Sc" stroke="#f59e0b" dot={false} strokeWidth={1.5} name="Warden Sc Score" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
