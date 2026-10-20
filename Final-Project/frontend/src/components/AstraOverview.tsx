import React, { useEffect, useRef } from 'react'
import {
  Activity,
  Radio,
  Wifi,
  ShieldCheck,
  TrendingUp,
  Cpu,
  ArrowRight,
  Database,
  BarChart2,
} from 'lucide-react'
import { AstraTab } from './AstraSidebar'

interface AstraOverviewProps {
  setActiveTab: (tab: AstraTab) => void
  isBackendHealthy: boolean
}

export function AstraOverview({ setActiveTab, isBackendHealthy }: AstraOverviewProps) {
  const waveCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const specCanvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    // Render static or subtle ambient animated mini previews
    const waveCanvas = waveCanvasRef.current
    if (waveCanvas) {
      const ctx = waveCanvas.getContext('2d')
      if (ctx) {
        const w = waveCanvas.width
        const h = waveCanvas.height
        ctx.clearRect(0, 0, w, h)

        // Subtle grid
        ctx.strokeStyle = 'rgba(124, 137, 162, 0.15)'
        ctx.lineWidth = 1
        ctx.beginPath()
        for (let y = 0; y <= h; y += h / 3) {
          ctx.moveTo(0, y)
          ctx.lineTo(w, y)
        }
        ctx.stroke()

        // Mini waveform line
        ctx.beginPath()
        ctx.strokeStyle = '#286FE5'
        ctx.lineWidth = 1.8
        for (let x = 0; x < w; x++) {
          const val = Math.sin(x * 0.08) * 0.45 + Math.sin(x * 0.19) * 0.25
          const y = h / 2 - val * (h * 0.4)
          if (x === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        }
        ctx.stroke()
      }
    }

    const specCanvas = specCanvasRef.current
    if (specCanvas) {
      const ctx = specCanvas.getContext('2d')
      if (ctx) {
        const w = specCanvas.width
        const h = specCanvas.height
        ctx.clearRect(0, 0, w, h)

        // Mini spectrum plot
        ctx.beginPath()
        ctx.strokeStyle = '#168C9A'
        ctx.lineWidth = 1.8
        for (let x = 0; x < w; x++) {
          const center = w / 2
          const main = Math.exp(-Math.pow((x - center) / 14, 2)) * 0.7
          const noise = ((Math.sin(x * 12.3) * 43758.5) % 1) * 0.15
          const y = h - (0.15 + main + noise) * h
          if (x === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        }
        ctx.stroke()
      }
    }
  }, [])

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-[10px] font-extrabold uppercase tracking-widest text-[var(--accent)] mb-1">
            Operational Overview
          </div>
          <h1 className="text-2xl font-black tracking-tight text-[var(--ink)]">
            Signal Intelligence & Research Workspace
          </h1>
          <p className="text-xs text-[var(--muted)] mt-1 max-w-xl leading-relaxed">
            Autonomous post-quantum multi-hop tactical communications, low probability of intercept (LPI) neural waveforms, and real-time SDR spectrum analysis.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab('spectrum')}
            className="neo-btn neo-btn-primary flex items-center gap-2 text-xs font-bold px-4 py-2"
          >
            <Radio className="w-4 h-4" />
            <span>Open Spectrum & Waterfall Lab</span>
          </button>
        </div>
      </div>

      {/* Top 4 Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="neo-raised p-4 space-y-2">
          <div className="flex items-center justify-between text-xs text-[var(--muted)] font-bold">
            <span>Signal-to-Noise Ratio</span>
            <div className="w-7 h-7 rounded-lg neo-inset flex items-center justify-center text-[var(--accent)]">
              <Activity className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="text-2xl font-black tracking-tight text-[var(--ink)]">
            18.6 <span className="text-xs font-bold text-[var(--muted)]">dB</span>
          </div>
          <div className="text-[10px] text-emerald-600 dark:text-emerald-400 font-bold flex items-center gap-1">
            <TrendingUp className="w-3 h-3" />
            <span>Optimal Covert Link Margin</span>
          </div>
        </div>

        <div className="neo-raised p-4 space-y-2">
          <div className="flex items-center justify-between text-xs text-[var(--muted)] font-bold">
            <span>Center Frequency</span>
            <div className="w-7 h-7 rounded-lg neo-inset flex items-center justify-center text-[var(--cyan)]">
              <Radio className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="text-2xl font-black tracking-tight text-[var(--ink)]">
            2.484 <span className="text-xs font-bold text-[var(--muted)]">GHz</span>
          </div>
          <div className="text-[10px] text-[var(--muted)] font-semibold">
            ISM Channel 14 · USRP Tuned
          </div>
        </div>

        <div className="neo-raised p-4 space-y-2">
          <div className="flex items-center justify-between text-xs text-[var(--muted)] font-bold">
            <span>LPI Model Stealth</span>
            <div className="w-7 h-7 rounded-lg neo-inset flex items-center justify-center text-emerald-600">
              <ShieldCheck className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="text-2xl font-black tracking-tight text-[var(--ink)]">
            8 / 8 <span className="text-xs font-bold text-[var(--muted)]">EW Gates</span>
          </div>
          <div className="text-[10px] text-emerald-600 dark:text-emerald-400 font-bold">
            Optimal Electronic Protection
          </div>
        </div>

        <div className="neo-raised p-4 space-y-2">
          <div className="flex items-center justify-between text-xs text-[var(--muted)] font-bold">
            <span>Mesh Topology</span>
            <div className="w-7 h-7 rounded-lg neo-inset flex items-center justify-center text-purple-600">
              <Wifi className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="text-2xl font-black tracking-tight text-[var(--ink)]">
            5 <span className="text-xs font-bold text-[var(--muted)]">Relays Active</span>
          </div>
          <div className="text-[10px] text-[var(--muted)] font-semibold">
            Alpha → UAV-Alpha → Bravo (3 Hops)
          </div>
        </div>
      </div>

      {/* Quick Launch Cards (Click-to-Launch) */}
      <div>
        <div className="text-xs font-bold text-[var(--muted)] mb-3">Quick Workspaces</div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button
            onClick={() => setActiveTab('spectrum')}
            className="neo-raised p-4 text-left group flex items-start justify-between cursor-pointer"
          >
            <div className="space-y-1">
              <div className="w-9 h-9 rounded-xl neo-inset flex items-center justify-center text-[var(--accent)] mb-2">
                <Radio className="w-4 h-4" />
              </div>
              <div className="text-sm font-bold text-[var(--ink)]">Spectrum & Waterfall Lab</div>
              <p className="text-xs text-[var(--muted)]">
                Compare waveforms with vs. without LPI, with real-time 60 FPS waterfall display.
              </p>
            </div>
            <ArrowRight className="w-4 h-4 text-[var(--subtle)] group-hover:text-[var(--accent)] group-hover:translate-x-1 transition-all" />
          </button>

          <button
            onClick={() => setActiveTab('topology')}
            className="neo-raised p-4 text-left group flex items-start justify-between cursor-pointer"
          >
            <div className="space-y-1">
              <div className="w-9 h-9 rounded-xl neo-inset flex items-center justify-center text-purple-600 mb-2">
                <Wifi className="w-4 h-4" />
              </div>
              <div className="text-sm font-bold text-[var(--ink)]">3D Tactical Mesh Network</div>
              <p className="text-xs text-[var(--muted)]">
                Interactive Three.js visualizer with UAV orbital corridors and drill scenarios.
              </p>
            </div>
            <ArrowRight className="w-4 h-4 text-[var(--subtle)] group-hover:text-purple-600 group-hover:translate-x-1 transition-all" />
          </button>

          <button
            onClick={() => setActiveTab('messages')}
            className="neo-raised p-4 text-left group flex items-start justify-between cursor-pointer"
          >
            <div className="space-y-1">
              <div className="w-9 h-9 rounded-xl neo-inset flex items-center justify-center text-emerald-600 mb-2">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div className="text-sm font-bold text-[var(--ink)]">Post-Quantum Secure Messages</div>
              <p className="text-xs text-[var(--muted)]">
                ML-KEM-768 key encapsulation with authenticated AES-256-GCM v3 envelopes.
              </p>
            </div>
            <ArrowRight className="w-4 h-4 text-[var(--subtle)] group-hover:text-emerald-600 group-hover:translate-x-1 transition-all" />
          </button>
        </div>
      </div>

      {/* Mini Previews & Comparison Matrix */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Signal Previews */}
        <div className="neo-raised p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-[var(--ink)]">Live Waveform & Spectrum Status</h3>
              <p className="text-xs text-[var(--muted)]">Time and frequency domain indicators</p>
            </div>
            <button
              onClick={() => setActiveTab('spectrum')}
              className="neo-btn text-xs font-semibold py-1 px-2.5"
            >
              Analyze in Lab
            </button>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <span className="text-[11px] font-bold text-[var(--muted)]">Time Domain (I/Q)</span>
              <div className="h-28 rounded-xl neo-inset p-1.5 flex items-center justify-center overflow-hidden">
                <canvas ref={waveCanvasRef} width={280} height={100} className="w-full h-full" />
              </div>
            </div>
            <div className="space-y-1">
              <span className="text-[11px] font-bold text-[var(--muted)]">Power Spectrum</span>
              <div className="h-28 rounded-xl neo-inset p-1.5 flex items-center justify-center overflow-hidden">
                <canvas ref={specCanvasRef} width={280} height={100} className="w-full h-full" />
              </div>
            </div>
          </div>
        </div>

        {/* Signal Profile Comparison Table */}
        <div className="neo-raised p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-[var(--ink)]">Signal Profile & Evasion Matrix</h3>
              <p className="text-xs text-[var(--muted)]">Modulation versus LPI stealth performance</p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-[var(--line)] text-[var(--muted)] font-extrabold uppercase text-[10px]">
                  <th className="pb-2">Waveform</th>
                  <th className="pb-2">Bandwidth</th>
                  <th className="pb-2">SNR Margin</th>
                  <th className="pb-2">EW Intercept Risk</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--line)]">
                <tr>
                  <td className="py-2.5 font-bold">Standard Carrier (No LPI)</td>
                  <td className="py-2.5 text-[var(--muted)]">12.5 kHz</td>
                  <td className="py-2.5 text-red-500 font-bold">+22.5 dB</td>
                  <td className="py-2.5 text-red-500 font-bold">CRITICAL (99.4%)</td>
                </tr>
                <tr>
                  <td className="py-2.5 font-bold">DSSS (Spreading 64)</td>
                  <td className="py-2.5 text-[var(--muted)]">2.0 MHz</td>
                  <td className="py-2.5 text-emerald-500 font-bold">−8.2 dB</td>
                  <td className="py-2.5 text-emerald-500 font-bold">LOW (3.2%)</td>
                </tr>
                <tr>
                  <td className="py-2.5 font-bold">FHSS (500 hops/s)</td>
                  <td className="py-2.5 text-[var(--muted)]">5.0 MHz</td>
                  <td className="py-2.5 text-emerald-500 font-bold">−4.5 dB</td>
                  <td className="py-2.5 text-emerald-500 font-bold">LOW (1.8%)</td>
                </tr>
                <tr>
                  <td className="py-2.5 font-bold text-[var(--accent)]">
                    ASTRA LPI-CGAN (Neural)
                  </td>
                  <td className="py-2.5 text-[var(--muted)]">2.4576 MHz</td>
                  <td className="py-2.5 text-cyan-600 dark:text-cyan-400 font-extrabold">
                    −12.4 dB
                  </td>
                  <td className="py-2.5 text-cyan-600 dark:text-cyan-400 font-extrabold">
                    COVERT (&lt; 0.05%)
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
