import React, { useState } from 'react'
import {
  Layers,
  Activity,
  Zap,
  Sliders,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  AreaChart,
  Area,
} from 'recharts'
import { ChannelSimulationResult } from '../../types'
import { api } from '../../services/api'

export const ChannelLabView: React.FC = () => {
  const [targetSnr, setTargetSnr] = useState<number>(6.0)
  const [cfoHz, setCfoHz] = useState<number>(45.0)
  const [phaseOffset, setPhaseOffset] = useState<number>(20.0)
  const [multipath, setMultipath] = useState<boolean>(false)
  const [isSimulating, setIsSimulating] = useState<boolean>(false)
  const [simResult, setSimResult] = useState<ChannelSimulationResult | null>(null)

  const handleRunSimulation = async () => {
    setIsSimulating(true)
    try {
      const res = await api.simulateChannel(targetSnr, cfoHz, phaseOffset, multipath)
      setSimResult(res)
    } catch (err) {
      console.warn('Simulation error:', err)
    } finally {
      setIsSimulating(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-zinc-900/80 border border-zinc-800 p-4 rounded-xl flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2">
            <Layers className="w-5 h-5 text-purple-400" />
            <h2 className="text-base font-bold font-mono text-zinc-100">
              Channel Simulation &amp; AWGN Impairment Lab
            </h2>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5 font-sans">
            Add AWGN, carrier frequency offset (CFO), phase rotation, and multipath fading to evaluate signal robustness
          </p>
        </div>

        <button
          onClick={handleRunSimulation}
          disabled={isSimulating}
          className="px-5 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-800 text-white font-mono text-xs font-bold flex items-center space-x-2 transition-colors shadow-md"
        >
          <Play className="w-4 h-4" />
          <span>{isSimulating ? 'Simulating...' : 'Run Simulation'}</span>
        </button>
      </div>

      {/* Parameter Control Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Target SNR */}
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-2 font-mono text-xs">
          <div className="flex justify-between">
            <span className="text-zinc-400">Target SNR:</span>
            <span className="text-cyan-400 font-bold">{targetSnr.toFixed(1)} dB</span>
          </div>
          <input
            type="range"
            min={-6}
            max={14}
            step={0.5}
            value={targetSnr}
            onChange={(e) => setTargetSnr(Number(e.target.value))}
            className="w-full accent-cyan-500 cursor-pointer"
          />
          <div className="flex justify-between text-[9px] text-zinc-500">
            <span>-6 dB (Sub-noise)</span>
            <span>+14 dB (Clean)</span>
          </div>
        </div>

        {/* CFO */}
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-2 font-mono text-xs">
          <div className="flex justify-between">
            <span className="text-zinc-400">Carrier Offset (CFO):</span>
            <span className="text-amber-400 font-bold">{cfoHz.toFixed(0)} Hz</span>
          </div>
          <input
            type="range"
            min={-150}
            max={150}
            step={5}
            value={cfoHz}
            onChange={(e) => setCfoHz(Number(e.target.value))}
            className="w-full accent-amber-500 cursor-pointer"
          />
          <div className="flex justify-between text-[9px] text-zinc-500">
            <span>-150 Hz</span>
            <span>+150 Hz</span>
          </div>
        </div>

        {/* Phase Offset */}
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-2 font-mono text-xs">
          <div className="flex justify-between">
            <span className="text-zinc-400">Phase Rotation:</span>
            <span className="text-purple-400 font-bold">{phaseOffset.toFixed(0)}&deg;</span>
          </div>
          <input
            type="range"
            min={0}
            max={180}
            step={5}
            value={phaseOffset}
            onChange={(e) => setPhaseOffset(Number(e.target.value))}
            className="w-full accent-purple-500 cursor-pointer"
          />
          <div className="flex justify-between text-[9px] text-zinc-500">
            <span>0&deg;</span>
            <span>180&deg;</span>
          </div>
        </div>

        {/* Multipath Fading */}
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl flex flex-col justify-between font-mono text-xs">
          <span className="text-zinc-400">Multipath Profile:</span>
          <label className="flex items-center space-x-2 cursor-pointer my-1">
            <input
              type="checkbox"
              checked={multipath}
              onChange={(e) => setMultipath(e.target.checked)}
              className="w-4 h-4 rounded border-zinc-700 bg-zinc-900 text-purple-500"
            />
            <span className="text-zinc-200">2-Ray Rayleigh Fading</span>
          </label>
          <span className="text-[9px] text-zinc-500">
            {multipath ? 'Tap 1: 1.0, Tap 2: 0.3' : 'Flat single-path AWGN'}
          </span>
        </div>
      </div>

      {/* Measured Numerical Verification Strip */}
      {simResult && (
        <div className="p-3 bg-zinc-950 border border-zinc-800 rounded-xl flex flex-wrap items-center justify-between text-xs font-mono gap-3">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span className="text-zinc-400">Channel Modeled Successfully:</span>
            <span className="text-cyan-400 font-bold">
              Target SNR: {simResult.channel_parameters.target_snr_db.toFixed(1)} dB &bull; Measured: {simResult.channel_parameters.measured_snr_db.toFixed(2)} dB
            </span>
          </div>
          <div className="flex items-center space-x-4 text-zinc-400 text-[11px]">
            <span>Noise Variance: <strong className="text-zinc-200">{simResult.channel_parameters.noise_variance}</strong></span>
            <span>Signal Power: <strong className="text-zinc-200">{simResult.channel_parameters.signal_power}</strong></span>
          </div>
        </div>
      )}

      {/* Before and After Visualizations */}
      {simResult && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Clean Waveform (Before) */}
          <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-400 font-mono">
              Before Impairment: Clean Synthesized Waveform
            </h3>
            <div className="h-60 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={simResult.clean_waveform_preview}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis dataKey="sample" stroke="#71717a" fontSize={11} />
                  <YAxis stroke="#71717a" fontSize={11} domain={[-1.5, 1.5]} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', fontSize: '11px', fontFamily: 'monospace' }}
                  />
                  <Line type="monotone" dataKey="i" stroke="#10b981" dot={false} strokeWidth={2} name="I (Clean)" />
                  <Line type="monotone" dataKey="q" stroke="#38bdf8" dot={false} strokeWidth={2} name="Q (Clean)" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Impaired Waveform (After) */}
          <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-purple-400 font-mono">
              After Impairment: Channel Degraded Signal (AWGN + CFO)
            </h3>
            <div className="h-60 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={simResult.distorted_waveform_preview}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis dataKey="sample" stroke="#71717a" fontSize={11} />
                  <YAxis stroke="#71717a" fontSize={11} domain={[-2.0, 2.0]} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', fontSize: '11px', fontFamily: 'monospace' }}
                  />
                  <Line type="monotone" dataKey="i" stroke="#a855f7" dot={false} strokeWidth={2} name="I (Impaired)" />
                  <Line type="monotone" dataKey="q" stroke="#ec4899" dot={false} strokeWidth={2} name="Q (Impaired)" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
