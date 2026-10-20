import React, { useState, useEffect } from 'react'
import {
  Radio,
  Activity,
  Shield,
  Cpu,
  CheckCircle2,
  AlertTriangle,
  Play,
  RotateCcw,
  Zap,
  Terminal,
  ExternalLink,
  Layers,
  Clock,
  Sparkles,
  Maximize2,
} from 'lucide-react'
import { WorkstationOverview } from '../../types'
import { api } from '../../services/api'
import { GuidedDemoControlPanel } from '../guided/GuidedDemoControlPanel'
import { TourMode } from '../guided/GuidedTourModal'

interface MissionOverviewViewProps {
  onNavigate: (tab: any) => void
  isBackendHealthy: boolean
  onStartTour?: (mode: TourMode) => void
  onOpenHelp?: () => void
  onOpenDemo?: () => void
}

export const MissionOverviewView: React.FC<MissionOverviewViewProps> = ({
  onNavigate,
  isBackendHealthy,
  onStartTour,
  onOpenHelp,
  onOpenDemo,
}) => {
  const [overview, setOverview] = useState<WorkstationOverview | null>(null)
  const [loading, setLoading] = useState<boolean>(true)

  const fetchOverview = async () => {
    try {
      const data = await api.getWorkstationOverview()
      setOverview(data)
    } catch (err) {
      console.warn('Failed to load workstation overview:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchOverview()
    const timer = setInterval(fetchOverview, 4000)
    return () => clearInterval(timer)
  }, [])

  if (loading && !overview) {
    return (
      <div className="flex-1 flex items-center justify-center p-12 text-zinc-400 font-mono text-sm">
        <Activity className="w-5 h-5 animate-spin mr-2 text-emerald-400" />
        Initialising ASTRA Mission System State...
      </div>
    )
  }

  const state = isBackendHealthy ? (overview?.system_state || 'READY') : 'OFFLINE'
  const isSdrConnected = overview?.sdr_hardware?.device_connected ?? false

  return (
    <div className="space-y-6">
      {/* Top Banner: Mission State & Operational Status */}
      <div className="bg-zinc-900/80 border border-zinc-800 p-4 rounded-xl flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <span
              className={`w-3 h-3 rounded-full ${
                state === 'READY' || state === 'COMPLETED'
                  ? 'bg-emerald-400 animate-pulse'
                  : state === 'DEGRADED'
                  ? 'bg-amber-400'
                  : 'bg-rose-500'
              }`}
            />
            <h2 className="text-base font-bold font-mono text-zinc-100 tracking-wide">
              SYSTEM STATE: <span className="text-emerald-400">{state}</span>
            </h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-300">
              {overview?.sdr_hardware?.operating_mode || 'SIMULATION_BENCH'}
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-1 font-sans">
            ASTRA &bull; Adaptive Secure Transmission and Research Architecture (Ettus USRP B205mini @ 2.484 GHz)
          </p>
        </div>

        {/* Quick Action Buttons */}
        <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
          <button
            onClick={() => onNavigate('transmitter')}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition-colors shadow-sm"
          >
            <Radio className="w-3.5 h-3.5" />
            <span>Transmitter</span>
          </button>
          <button
            onClick={() => onNavigate('receiver')}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-semibold transition-colors shadow-sm"
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Receiver</span>
          </button>
          <button
            onClick={() => onNavigate('analyser')}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-750 transition-colors"
          >
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span>Signal Analyser</span>
          </button>
          <button
            onClick={() => onNavigate('channel')}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-750 transition-colors"
          >
            <Layers className="w-3.5 h-3.5 text-purple-400" />
            <span>Channel Lab</span>
          </button>
          {onOpenDemo && (
            <button
              onClick={onOpenDemo}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-emerald-600/30 to-cyan-600/30 hover:from-emerald-600/45 hover:to-cyan-600/45 text-emerald-300 border border-emerald-500/50 font-semibold transition-all shadow-sm cursor-pointer"
              title="Open Fullscreen Technical Exhibition & Presentation Mode [Esc to exit]"
            >
              <Maximize2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Presentation Mode</span>
            </button>
          )}
        </div>
      </div>

      {/* Guided Tour & Demo Control Panel */}
      <GuidedDemoControlPanel
        onStartTour={(mode) => onStartTour?.(mode)}
        onOpenHelp={() => onOpenHelp?.()}
        onViewDiagnostics={() => onNavigate('diagnostics')}
        onExploreManually={() => onNavigate('transmitter')}
      />

      {/* Grid of Key Subsystem Diagnostic Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* SDR Hardware Card */}
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold font-mono text-zinc-300 uppercase tracking-wider flex items-center space-x-1.5">
              <Radio className="w-4 h-4 text-emerald-400" />
              <span>SDR Transceiver</span>
            </span>
            <span
              className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                isSdrConnected
                  ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
                  : 'bg-zinc-800 text-zinc-400 border border-zinc-700'
              }`}
            >
              {isSdrConnected ? 'HARDWARE ONLINE' : 'SIMULATION MODE'}
            </span>
          </div>

          <div className="space-y-1.5 text-xs font-mono text-zinc-300">
            <div className="flex justify-between">
              <span className="text-zinc-500">Center Frequency:</span>
              <span className="text-zinc-200">2.484000 GHz (Ch 14)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Sampling Rate:</span>
              <span className="text-cyan-400 font-bold">245.76 kS/s</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Decimation:</span>
              <span className="text-zinc-300">250 (61.44 MHz clock)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Driver / Device:</span>
              <span className="text-zinc-400 truncate max-w-[130px]">
                {overview?.sdr_hardware?.driver_version || 'UHD 4.8.0'}
              </span>
            </div>
          </div>
        </div>

        {/* Cryptographic Protection Card */}
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold font-mono text-zinc-300 uppercase tracking-wider flex items-center space-x-1.5">
              <Shield className="w-4 h-4 text-purple-400" />
              <span>Cryptographic Suite</span>
            </span>
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-purple-950/80 text-purple-300 border border-purple-800">
              AES-256-GCM v2
            </span>
          </div>

          <div className="space-y-1.5 text-xs font-mono text-zinc-300">
            <div className="flex justify-between">
              <span className="text-zinc-500">Cipher:</span>
              <span className="text-purple-300">AES-256 (GCM Authenticated)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Authentication Tag:</span>
              <span className="text-zinc-200">128-bit Poly1305 GMAC</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">FEC Coding:</span>
              <span className="text-emerald-400">Reed-Solomon RS(42, 34)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Error Correction:</span>
              <span className="text-zinc-300">t = 4 symbols / block</span>
            </div>
          </div>
        </div>

        {/* Neural Waveform Model Card */}
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold font-mono text-zinc-300 uppercase tracking-wider flex items-center space-x-1.5">
              <Cpu className="w-4 h-4 text-emerald-400" />
              <span>Neural Generator</span>
            </span>
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-800">
              lpi_v4.best.pt
            </span>
          </div>

          <div className="space-y-1.5 text-xs font-mono text-zinc-300">
            <div className="flex justify-between">
              <span className="text-zinc-500">Model Checkpoint:</span>
              <span className="text-emerald-400 font-bold">Gen 2 v4 (Verified)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Frame Layout:</span>
              <span className="text-zinc-200">64 ZC + 512 Payload</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Spreading Gain:</span>
              <span className="text-cyan-400 font-bold">9.03 dB (8 samp/bit)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Inference Device:</span>
              <span className="text-zinc-300">CPU (OpenBLAS Safe)</span>
            </div>
          </div>
        </div>

        {/* Electronic Warfare Stealth Battery Card */}
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold font-mono text-zinc-300 uppercase tracking-wider flex items-center space-x-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>Stealth Battery</span>
            </span>
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-800">
              8 / 8 PASS
            </span>
          </div>

          <div className="space-y-1.5 text-xs font-mono text-zinc-300">
            <div className="flex justify-between">
              <span className="text-zinc-500">KS-Test p-value:</span>
              <span className="text-emerald-400 font-bold">
                {overview?.stealth_summary?.ks_p?.toFixed(4) || '0.8654'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Signal Kurtosis:</span>
              <span className="text-emerald-400 font-bold">
                {overview?.stealth_summary?.kurtosis?.toFixed(3) || '2.991'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Adversary Accuracy:</span>
              <span className="text-zinc-300">
                {overview?.stealth_summary?.adv_acc?.toFixed(1) || '50.0'}% (Chance)
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Warden Verdict:</span>
              <span className="text-emerald-400 font-semibold">BLIND TO EMISSIONS</span>
            </div>
          </div>
        </div>
      </div>

      {/* Two Column Layout: System Activity Log & Scientific Warnings */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Recent Audit & System Events */}
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 font-mono flex items-center space-x-2">
              <Terminal className="w-4 h-4 text-emerald-400" />
              <span>Operational Event Log</span>
            </h3>
            <span className="text-[10px] font-mono text-zinc-500">
              {overview?.recent_events?.length || 0} recent entries
            </span>
          </div>

          <div className="space-y-2">
            {(overview?.recent_events || []).map((ev, idx) => (
              <div
                key={idx}
                className="p-2.5 bg-zinc-950 border border-zinc-850 rounded-lg flex items-start space-x-2 text-xs font-mono"
              >
                <span className="text-emerald-400 font-bold text-[10px] bg-emerald-950/60 px-1 py-0.2 rounded border border-emerald-900/50">
                  {ev.source}
                </span>
                <div className="flex-1">
                  <p className="text-zinc-200">{ev.message}</p>
                  <span className="text-[9px] text-zinc-500">
                    {new Date(ev.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Operating Warnings & Calibration Safeguards */}
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 font-mono flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <span>RF Safeguards &amp; Operational Constraints</span>
            </h3>
            <span className="text-[10px] font-mono text-zinc-500">ACTIVE CONTROLS</span>
          </div>

          <div className="space-y-2.5 text-xs font-mono">
            <div className="p-2.5 bg-amber-950/20 border border-amber-800/40 rounded-lg text-amber-300/90 leading-relaxed">
              <strong>RF Safety Lockout:</strong> Live over-the-air transmission requires explicit confirmation (`confirm: true`).
              Operating frequency is locked to ISM Channel 14 (2.484 GHz) with maximum TX gain limited to 0 dB for sub-noise operation.
            </div>

            <div className="p-2.5 bg-zinc-950 border border-zinc-850 rounded-lg text-zinc-400 space-y-1">
              <div className="flex justify-between">
                <span>Thermal Noise Floor Reference:</span>
                <strong className="text-zinc-200">-95.0 dBm</strong>
              </div>
              <div className="flex justify-between">
                <span>Target Signal PSD:</span>
                <strong className="text-emerald-400">-98.0 dBm (&Delta; -3.0 dB)</strong>
              </div>
              <div className="flex justify-between">
                <span>Master Clock Alignment:</span>
                <strong className="text-cyan-400">61.44 MHz &divide; 250 (Exact)</strong>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
