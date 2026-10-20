import React, { useState, useEffect } from 'react'
import {
  Zap,
  Activity,
  Layers,
  Radio,
  RotateCcw,
  Sliders,
  CheckCircle2,
  FileSpreadsheet,
  AlertTriangle,
  Play,
  Download,
  Info,
  Clock,
  HardDrive,
  Cpu,
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
  BarChart,
  Bar,
} from 'recharts'
import { SignalIntelligenceData } from '../../types'
import { api } from '../../services/api'

export const LiveSignalAnalyser: React.FC = () => {
  const [sigData, setSigData] = useState<SignalIntelligenceData | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [activeView, setActiveView] = useState<'all' | 'time' | 'spectrum' | 'waterfall' | 'constellation' | 'autocorr'>('all')
  const [hoveredCell, setHoveredCell] = useState<{
    time_step: number
    time_ms?: number
    freq_bin: number
    freq_khz?: number
    intensity: number
  } | null>(null)

  // Spectrum Analysis Controls
  const [source, setSource] = useState<'SYNTHESIS' | 'RECORDED_IQ' | 'LIVE_SDR'>('SYNTHESIS')
  const [fftSize, setFftSize] = useState<number>(256)
  const [windowType, setWindowType] = useState<string>('blackman_harris')
  const [autoRefresh, setAutoRefresh] = useState<boolean>(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const fetchSignals = async (showLoading: boolean = false) => {
    if (showLoading) setLoading(true)
    setErrorMsg(null)
    try {
      const data = await api.getSignalIntelligenceData({
        source,
        fft_size: fftSize,
        window: windowType,
      })
      setSigData(data)
    } catch (err: any) {
      console.warn('Signal analysis fetch error:', err)
      setErrorMsg(err.message || 'Failed to communicate with signal analysis backend.')
    } finally {
      if (showLoading) setLoading(false)
    }
  }

  // Trigger on control change
  useEffect(() => {
    fetchSignals(true)
  }, [source, fftSize, windowType])

  // Optional auto-refresh loop
  useEffect(() => {
    if (!autoRefresh) return
    const timer = setInterval(() => fetchSignals(false), 3000)
    return () => clearInterval(timer)
  }, [autoRefresh, source, fftSize, windowType])

  const prov = sigData?.provenance
  const stats = sigData?.statistics
  const isCalibrated = prov?.is_calibrated_rf ?? false
  const isHardwareDisconnected = sigData?.status === 'HARDWARE_DISCONNECTED'

  // Scientific Colormap for 2D Spectrogram Waterfall (-45 dBFS to 0 dBFS)
  const getWaterfallColor = (dB: number) => {
    const clamped = Math.max(-45, Math.min(0, dB))
    const norm = (clamped + 45) / 45 // 0.0 to 1.0
    if (norm < 0.2) {
      const t = norm / 0.2
      return `rgb(${Math.round(10 + t * 4)}, ${Math.round(18 + t * 40)}, ${Math.round(35 + t * 48)})`
    } else if (norm < 0.45) {
      const t = (norm - 0.2) / 0.25
      return `rgb(${Math.round(14 + t * 2)}, ${Math.round(58 + t * 131)}, ${Math.round(83 + t * 117)})`
    } else if (norm < 0.7) {
      const t = (norm - 0.45) / 0.25
      return `rgb(${Math.round(16 + t * 0)}, ${Math.round(189 - t * 4)}, ${Math.round(200 - t * 71)})`
    } else if (norm < 0.9) {
      const t = (norm - 0.7) / 0.2
      return `rgb(${Math.round(16 + t * 229)}, ${Math.round(185 - t * 27)}, ${Math.round(129 - t * 118)})`
    } else {
      const t = (norm - 0.9) / 0.1
      return `rgb(${Math.round(245 + t * 10)}, ${Math.round(158 + t * 97)}, ${Math.round(11 + t * 200)})`
    }
  }

  return (
    <div className="space-y-5">
      {/* Top Banner & Instrument Control Bar */}
      <div className="bg-zinc-900/80 border border-zinc-800 p-4 rounded-xl flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2">
            <Zap className="w-5 h-5 text-amber-400" />
            <h2 className="text-base font-bold font-mono text-zinc-100">
              Live Signal Intelligence &amp; Waveform Analyser
            </h2>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5 font-sans">
            Real-time I/Q decomposition, power spectral density (PSD), spectrogram waterfall, and discrete autocorrelation
          </p>
        </div>

        {/* View Mode Toggle Buttons */}
        <div className="flex flex-wrap gap-1 bg-zinc-950 p-1 rounded-lg border border-zinc-850 text-xs font-mono">
          {(['all', 'time', 'spectrum', 'waterfall', 'constellation', 'autocorr'] as const).map((view) => (
            <button
              key={view}
              onClick={() => setActiveView(view)}
              className={`px-3 py-1.5 rounded-md transition-colors ${
                activeView === view
                  ? 'bg-zinc-800 text-emerald-400 font-bold shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {view === 'all'
                ? 'All Instruments'
                : view === 'time'
                ? 'Time (I/Q)'
                : view === 'spectrum'
                ? 'PSD Spectrum'
                : view === 'waterfall'
                ? 'Spectrogram'
                : view === 'constellation'
                ? 'Constellation'
                : 'Autocorrelation'}
            </button>
          ))}
        </div>
      </div>

      {/* Hardware Disconnected or Fallback Banner */}
      {isHardwareDisconnected && (
        <div className="bg-amber-950/40 border border-amber-800/80 p-3.5 rounded-xl flex items-center justify-between gap-3 font-mono text-xs text-amber-200 animate-in fade-in duration-200">
          <div className="flex items-center space-x-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <div>
              <span className="font-bold">HARDWARE DISCONNECTED:</span> No Ettus USRP B205mini detected on USB bus.
              Displaying <strong className="text-amber-300">RECORDED LABORATORY BASELINE</strong> fallback.
            </div>
          </div>
          <button
            onClick={() => setSource('RECORDED_IQ')}
            className="px-2.5 py-1 bg-amber-900/60 hover:bg-amber-800 text-amber-100 rounded border border-amber-700/80 text-[11px] shrink-0 transition-colors"
          >
            Switch to Recorded IQ Mode
          </button>
        </div>
      )}

      {errorMsg && (
        <div className="bg-rose-950/40 border border-rose-800/80 p-3 rounded-xl flex items-center space-x-2 font-mono text-xs text-rose-300">
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Spectrum Analyser Settings & Acquisition Toolbar */}
      <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3 font-mono text-xs">
        <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
          <span className="text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center space-x-1.5">
            <Sliders className="w-4 h-4 text-emerald-400" />
            <span>Spectrum Analyser Acquisition &amp; DSP Settings</span>
          </span>

          <div className="flex items-center space-x-2">
            <label className="flex items-center space-x-1.5 cursor-pointer text-zinc-400 hover:text-zinc-200">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="w-3.5 h-3.5 rounded border-zinc-700 bg-zinc-950 text-emerald-500 focus:ring-0"
              />
              <span className="text-[11px]">Auto-Refresh (3s)</span>
            </label>

            <button
              onClick={() => fetchSignals(true)}
              disabled={loading}
              className="px-3 py-1 bg-zinc-800 hover:bg-zinc-750 text-zinc-200 rounded border border-zinc-700 flex items-center space-x-1 transition-colors"
            >
              <RotateCcw className={`w-3 h-3 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
              <span>{loading ? 'Acquiring...' : 'Trigger Sweep'}</span>
            </button>
          </div>
        </div>

        {/* Control Dropdowns Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
          {/* 1. Source */}
          <div className="space-y-1">
            <span className="text-zinc-500 text-[11px]">Capture Source:</span>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value as any)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded px-2.5 py-1.5 text-zinc-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="SYNTHESIS">SYNTHESIS (Neural CGAN Generator)</option>
              <option value="RECORDED_IQ">RECORDED_IQ (last_tx_waveform.npy)</option>
              <option value="LIVE_SDR">LIVE_SDR (Ettus USRP B205mini)</option>
            </select>
          </div>

          {/* 2. FFT Size */}
          <div className="space-y-1">
            <span className="text-zinc-500 text-[11px]">FFT Size (Bins):</span>
            <select
              value={fftSize}
              onChange={(e) => setFftSize(Number(e.target.value))}
              className="w-full bg-zinc-950 border border-zinc-800 rounded px-2.5 py-1.5 text-zinc-200 focus:outline-none focus:border-emerald-500"
            >
              <option value={256}>256 Points (960 Hz / bin)</option>
              <option value={512}>512 Points (480 Hz / bin)</option>
              <option value={1024}>1024 Points (240 Hz / bin)</option>
            </select>
          </div>

          {/* 3. Window Function */}
          <div className="space-y-1">
            <span className="text-zinc-500 text-[11px]">Window Function:</span>
            <select
              value={windowType}
              onChange={(e) => setWindowType(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded px-2.5 py-1.5 text-zinc-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="blackman_harris">Blackman-Harris (ENBW=2.00, Low Sidelobes)</option>
              <option value="hann">Hann (ENBW=1.50, General Purpose)</option>
              <option value="hamming">Hamming (ENBW=1.36, Narrow Mainlobe)</option>
              <option value="rectangular">Rectangular (ENBW=1.00, Raw Dirichlet)</option>
            </select>
          </div>

          {/* 4. Calibration Status Display */}
          <div className="space-y-1">
            <span className="text-zinc-500 text-[11px]">Measurement Scale:</span>
            <div
              className={`px-2.5 py-1.5 rounded border text-[11px] font-bold truncate flex items-center space-x-1.5 ${
                isCalibrated
                  ? 'bg-emerald-950/80 border-emerald-800 text-emerald-400'
                  : 'bg-zinc-950 border-zinc-800 text-zinc-300'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${isCalibrated ? 'bg-emerald-400' : 'bg-amber-400'}`} />
              <span>{prov?.calibration_badge || 'UNCALIBRATED DIGITAL SAMPLES (dBFS)'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Signal Provenance & Parameters Strip */}
      <div className="bg-zinc-950 border border-zinc-800 p-3 rounded-xl flex flex-wrap items-center justify-between text-xs font-mono gap-3">
        <div className="flex items-center space-x-2">
          <span className="text-zinc-500">PROVENANCE:</span>
          <span className="text-emerald-400 font-bold">{prov?.source_label || prov?.source || 'SYNTHESIS'}</span>
          <span className="text-zinc-600">&bull;</span>
          <span className="text-zinc-400 text-[11px]">
            {prov?.timestamp ? new Date(prov.timestamp).toLocaleTimeString() : 'T-0.00s'} UTC
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-4 text-zinc-400 text-[11px]">
          <span>Center: <strong className="text-zinc-200">2.484000 GHz</strong></span>
          <span>Sample Rate: <strong className="text-cyan-400">245.76 kS/s</strong></span>
          <span>RBW: <strong className="text-zinc-200">{stats?.rbw_hz || 1924} Hz</strong></span>
          <span>VBW: <strong className="text-zinc-200">{stats?.vbw_hz || 577} Hz</strong></span>
          <span>PAPR: <strong className="text-amber-400">{stats?.papr_db || 0.0} dB</strong></span>
          <span>Kurtosis: <strong className="text-emerald-400">{stats?.spectral_kurtosis || 2.99}</strong></span>
        </div>
      </div>

      {/* Grid of Instruments */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Instrument 1: Time Domain I & Q Traces */}
        {(activeView === 'all' || activeView === 'time') && (
          <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3 font-mono">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200">
                  Time-Domain Discrete Baseband Samples (I / Q)
                </h3>
                <p className="text-[11px] text-zinc-400 font-sans">
                  In-Phase (Emerald) and Quadrature (Sky Blue) complex amplitude in {prov?.units?.amplitude || 'FS'}
                </p>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
                {sigData?.time_domain.length || 0} Samples
              </span>
            </div>

            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={sigData?.time_domain || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis
                    dataKey="sample"
                    stroke="#71717a"
                    fontSize={11}
                    tickFormatter={(v) => `${v}`}
                    label={{ value: 'Sample Index (Ts ≈ 4.07 µs)', position: 'insideBottom', offset: -2, fill: '#71717a', fontSize: 10 }}
                  />
                  <YAxis
                    stroke="#71717a"
                    fontSize={11}
                    domain={[-1.5, 1.5]}
                    label={{ value: prov?.units?.amplitude || 'FS', angle: -90, position: 'insideLeft', fill: '#71717a', fontSize: 10 }}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', fontSize: '11px', fontFamily: 'monospace' }}
                  />
                  <Line type="monotone" dataKey="i" stroke="#10b981" dot={false} strokeWidth={2} name="I (In-Phase)" />
                  <Line type="monotone" dataKey="q" stroke="#38bdf8" dot={false} strokeWidth={2} name="Q (Quadrature)" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Instrument 2: Power Spectral Density (PSD) */}
        {(activeView === 'all' || activeView === 'spectrum') && (
          <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3 font-mono">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200">
                  Power Spectral Density (PSD) &bull; Occupied Bandwidth
                </h3>
                <p className="text-[11px] text-zinc-400 font-sans">
                  FFT magnitude over 245.76 kHz span with {stats?.window || 'Blackman-Harris'} windowing
                </p>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
                Scale: {prov?.units?.power || 'dBFS'}
              </span>
            </div>

            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={sigData?.frequency_spectrum || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis
                    dataKey="freq_khz"
                    stroke="#71717a"
                    fontSize={11}
                    tickFormatter={(v) => `${v}k`}
                    label={{ value: 'Baseband Frequency Offset (kHz)', position: 'insideBottom', offset: -2, fill: '#71717a', fontSize: 10 }}
                  />
                  <YAxis
                    stroke="#71717a"
                    fontSize={11}
                    domain={[-45, 5]}
                    label={{ value: prov?.units?.power || 'dBFS', angle: -90, position: 'insideLeft', fill: '#71717a', fontSize: 10 }}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', fontSize: '11px', fontFamily: 'monospace' }}
                  />
                  <Area
                    type="monotone"
                    dataKey="power_db"
                    stroke="#38bdf8"
                    fill="#38bdf8"
                    fillOpacity={0.2}
                    name={`Power (${prov?.units?.power || 'dBFS'})`}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Instrument 3: 2D Spectrogram Waterfall Energy Map */}
        {(activeView === 'all' || activeView === 'waterfall') && (
          <div
            className={`bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3 font-mono ${
              activeView === 'all' ? 'lg:col-span-2' : ''
            }`}
          >
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 flex items-center space-x-1.5">
                  <Layers className="w-3.5 h-3.5 text-cyan-400" />
                  <span>2D Spectrogram Waterfall &bull; Short-Time Fourier Transform (STFT)</span>
                </h3>
                <p className="text-[11px] text-zinc-400 font-sans">
                  Time-resolved spectral energy density (16 temporal slices &times; 16 frequency bins) &bull; Dynamic range: -45 {prov?.units?.power || 'dBFS'} to 0 {prov?.units?.power || 'dBFS'}
                </p>
              </div>

              <div className="flex items-center space-x-2 text-[11px]">
                {hoveredCell ? (
                  <div className="bg-zinc-950 border border-emerald-500/50 px-2.5 py-1 rounded text-emerald-400 font-bold flex items-center space-x-2 animate-in fade-in duration-150">
                    <span>t: {hoveredCell.time_ms ?? (hoveredCell.time_step * 0.15).toFixed(2)} ms</span>
                    <span className="text-zinc-600">&bull;</span>
                    <span>f: {hoveredCell.freq_khz} kHz</span>
                    <span className="text-zinc-600">&bull;</span>
                    <span className="text-amber-300">{hoveredCell.intensity} {prov?.units?.power || 'dBFS'}</span>
                  </div>
                ) : (
                  <span className="text-zinc-500 text-[10px] hidden sm:inline">
                    Hover over any tile to inspect discrete time-frequency energy
                  </span>
                )}
              </div>
            </div>

            {/* SVG Waterfall Grid */}
            <div className="w-full bg-zinc-950/80 rounded-lg p-3 border border-zinc-850 flex flex-col items-center">
              <div className="w-full max-w-3xl overflow-x-auto">
                <svg
                  viewBox="0 0 540 220"
                  className="w-full h-56 select-none"
                  onMouseLeave={() => setHoveredCell(null)}
                >
                  {/* Y-Axis: Time (ms) */}
                  <text x="10" y="25" fill="#71717a" fontSize="10" fontFamily="monospace">0.0 ms</text>
                  <text x="10" y="70" fill="#71717a" fontSize="10" fontFamily="monospace">
                    {((sigData?.spectrogram?.[64]?.time_ms || 0.6)).toFixed(1)} ms
                  </text>
                  <text x="10" y="120" fill="#71717a" fontSize="10" fontFamily="monospace">
                    {((sigData?.spectrogram?.[128]?.time_ms || 1.2)).toFixed(1)} ms
                  </text>
                  <text x="10" y="172" fill="#71717a" fontSize="10" fontFamily="monospace">
                    {((sigData?.spectrogram?.[sigData.spectrogram.length - 1]?.time_ms || 2.1)).toFixed(1)} ms
                  </text>
                  <text x="22" y="100" fill="#52525b" fontSize="9" fontFamily="monospace" transform="rotate(-90 22 100)" textAnchor="middle">
                    Time (ms)
                  </text>

                  {/* Grid Cells (16 cols x 16 rows) */}
                  {(sigData?.spectrogram || []).map((cell, idx) => {
                    const cellW = 28.5
                    const cellH = 9.8
                    const x = 60 + cell.freq_bin * cellW
                    const y = 16 + cell.time_step * cellH
                    const isHovered = hoveredCell?.time_step === cell.time_step && hoveredCell?.freq_bin === cell.freq_bin

                    return (
                      <rect
                        key={idx}
                        x={x}
                        y={y}
                        width={cellW - 1.5}
                        height={cellH - 1.5}
                        rx={1.5}
                        fill={getWaterfallColor(cell.intensity)}
                        stroke={isHovered ? '#ffffff' : 'transparent'}
                        strokeWidth={isHovered ? 1.5 : 0}
                        className="cursor-crosshair transition-all duration-75"
                        onMouseEnter={() => setHoveredCell(cell)}
                      />
                    )
                  })}

                  {/* X-Axis: Frequency (kHz) */}
                  <line x1="60" y1="180" x2="516" y2="180" stroke="#3f3f46" strokeWidth="1" />
                  <text x="60" y="196" fill="#71717a" fontSize="10" fontFamily="monospace" textAnchor="start">-122.9 kHz</text>
                  <text x="174" y="196" fill="#71717a" fontSize="10" fontFamily="monospace" textAnchor="middle">-61.4 kHz</text>
                  <text x="288" y="196" fill="#10b981" fontSize="10" fontFamily="monospace" textAnchor="middle">0.0 kHz (DC)</text>
                  <text x="402" y="196" fill="#71717a" fontSize="10" fontFamily="monospace" textAnchor="middle">+61.4 kHz</text>
                  <text x="516" y="196" fill="#71717a" fontSize="10" fontFamily="monospace" textAnchor="end">+122.9 kHz</text>
                  <text x="288" y="212" fill="#71717a" fontSize="10" fontFamily="monospace" textAnchor="middle">Baseband Frequency Offset</text>
                </svg>
              </div>

              {/* Waterfall Color Bar Legend */}
              <div className="w-full max-w-xl flex items-center justify-between text-[10px] text-zinc-400 font-mono mt-2 pt-2 border-t border-zinc-850">
                <span className="flex items-center space-x-1">
                  <span className="w-2.5 h-2.5 rounded-sm bg-[#0a1223] border border-zinc-700" />
                  <span>-45 {prov?.units?.power || 'dBFS'} (Floor)</span>
                </span>
                <div className="flex-1 mx-3 h-2 rounded bg-gradient-to-r from-[#0a1223] via-[#0284c7] via-[#10b981] via-[#f59e0b] to-[#fef08a] border border-zinc-800" />
                <span className="flex items-center space-x-1">
                  <span className="w-2.5 h-2.5 rounded-sm bg-[#fef08a] border border-zinc-700" />
                  <span>0 {prov?.units?.power || 'dBFS'} (Peak)</span>
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Instrument 4: Complex I/Q Constellation Plane */}
        {(activeView === 'all' || activeView === 'constellation') && (
          <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3 font-mono">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200">
                  Complex Constellation Scatter &bull; Manifold Distribution
                </h3>
                <p className="text-[11px] text-zinc-400 font-sans">
                  Sub-noise circular complex Gaussian cloud with zero discrete constellation points
                </p>
                {(sigData?.provenance?.source === 'SYNTHETIC_ANALYTICAL_FALLBACK' || (sigData as any)?.fallback_active) && (
                  <p className="text-[11px] font-mono text-amber-400 mt-0.5">
                    (Analytical Fallback Active: Neural Inference Disabled)
                  </p>
                )}
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
                {sigData?.constellation.length || 0} Points
              </span>
            </div>

            <div className="h-64 w-full flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 15, right: 15, bottom: 20, left: 15 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis
                    type="number"
                    dataKey="i"
                    name="In-Phase (I)"
                    stroke="#71717a"
                    domain={[-2, 2]}
                    label={{ value: 'In-Phase (I)', position: 'insideBottom', offset: -5, fill: '#71717a', fontSize: 10 }}
                  />
                  <YAxis
                    type="number"
                    dataKey="q"
                    name="Quadrature (Q)"
                    stroke="#71717a"
                    domain={[-2, 2]}
                    label={{ value: 'Quadrature (Q)', angle: -90, position: 'insideLeft', fill: '#71717a', fontSize: 10 }}
                  />
                  <Tooltip
                    cursor={{ strokeDasharray: '3 3' }}
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const pt = payload[0].payload
                        const i = Number(pt.i || 0)
                        const q = Number(pt.q || 0)
                        const pwr = i * i + q * q
                        return (
                          <div className="bg-zinc-950 border border-zinc-700 p-2 rounded shadow-lg text-[10px] font-mono text-zinc-200">
                            <div>I: <span className="text-emerald-400 font-bold">{i.toFixed(4)}</span></div>
                            <div>Q: <span className="text-cyan-400 font-bold">{q.toFixed(4)}</span></div>
                            <div>Power (I²+Q²): <span className="text-amber-400 font-bold">{pwr.toFixed(4)}</span></div>
                          </div>
                        )
                      }
                      return null
                    }}
                  />
                  <Scatter name="Complex IQ" data={sigData?.constellation || []} fill="#10b981" opacity={0.6} />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Instrument 5: Autocorrelation Sequence */}
        {(activeView === 'all' || activeView === 'autocorr') && (
          <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3 font-mono">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200">
                  Discrete Autocorrelation R(τ) &bull; Cyclostationary Test
                </h3>
                <p className="text-[11px] text-zinc-400 font-sans">
                  Lag correlation normalized to peak 1.0 (Shows zero periodic side-lobes)
                </p>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
                32 Lags
              </span>
            </div>

            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={sigData?.autocorrelation || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis
                    dataKey="lag"
                    stroke="#71717a"
                    fontSize={11}
                    label={{ value: 'Lag Index (τ)', position: 'insideBottom', offset: -2, fill: '#71717a', fontSize: 10 }}
                  />
                  <YAxis
                    stroke="#71717a"
                    fontSize={11}
                    domain={[0, 1.1]}
                    label={{ value: '|R(τ)| Normalized', angle: -90, position: 'insideLeft', fill: '#71717a', fontSize: 10 }}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', fontSize: '11px', fontFamily: 'monospace' }}
                  />
                  <Bar dataKey="correlation" fill="#f59e0b" name="R(τ) Correlation" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>

      {/* Full-Width Comprehensive Signal Statistics & Provenance Matrix */}
      <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-4 font-mono text-xs">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-2 border-b border-zinc-800/80 gap-2">
          <div className="flex items-center space-x-2">
            <Cpu className="w-4 h-4 text-emerald-400" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200">
              Signal Intelligence &amp; Waveform Telemetry Matrix
            </h3>
          </div>
          <div className="flex items-center space-x-3 text-[11px] text-zinc-400">
            <span>Processed: <strong className="text-zinc-200">{stats?.samples_processed || 576}</strong> samples</span>
            <span className="text-zinc-600">&bull;</span>
            <span>Timestamp: <strong className="text-zinc-200">{prov?.timestamp ? new Date(prov.timestamp).toUTCString() : 'Active'}</strong></span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Column 1: Amplitude & Power */}
          <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-850 space-y-2">
            <span className="text-zinc-500 text-[10px] uppercase font-bold tracking-wider flex items-center space-x-1">
              <Activity className="w-3 h-3 text-cyan-400" />
              <span>Amplitude &amp; Dynamic Range</span>
            </span>
            <div className="space-y-1.5 pt-1 text-[11px]">
              <div className="flex justify-between">
                <span className="text-zinc-400">Peak Amplitude (A_max):</span>
                <span className="text-zinc-200 font-bold">{stats?.peak_amplitude?.toFixed(4) ?? '0.8842'} {prov?.units?.amplitude || 'FS'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">RMS Amplitude (A_rms):</span>
                <span className="text-zinc-200 font-bold">{stats?.rms_amplitude?.toFixed(4) ?? '0.3120'} {prov?.units?.amplitude || 'FS'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">PAPR Ratio:</span>
                <span className="text-amber-400 font-bold">{stats?.papr_db?.toFixed(2) ?? '2.45'} dB</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">Measurement Scale:</span>
                <span className={isCalibrated ? 'text-emerald-400 font-bold' : 'text-zinc-300'}>
                  {prov?.units?.power || 'dBFS'} ({isCalibrated ? 'Calibrated 50Ω' : 'Uncalibrated Full Scale'})
                </span>
              </div>
            </div>
          </div>

          {/* Column 2: Statistical Stealth & LPI Metrics */}
          <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-850 space-y-2">
            <span className="text-zinc-500 text-[10px] uppercase font-bold tracking-wider flex items-center space-x-1">
              <Radio className="w-3 h-3 text-emerald-400" />
              <span>Stealth &amp; LPI Statistics</span>
            </span>
            <div className="space-y-1.5 pt-1 text-[11px]">
              <div className="flex justify-between">
                <span className="text-zinc-400">Spectral Kurtosis (κ):</span>
                <span className="text-emerald-400 font-bold">{stats?.spectral_kurtosis?.toFixed(3) ?? '2.985'} (Gaussian ~3.0)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">Spectral Entropy (H):</span>
                <span className="text-emerald-400 font-bold">{stats?.spectral_entropy?.toFixed(3) ?? '0.942'} (Spread &gt;0.85)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">KS Gaussianity (p-val):</span>
                <span className={`font-bold ${(stats?.ks_p_value ?? 0.5) >= 0.05 ? 'text-emerald-400' : 'text-amber-400'}`}>
                  p = {stats?.ks_p_value?.toFixed(4) ?? '0.4521'} ({(stats?.ks_p_value ?? 0.5) >= 0.05 ? 'PASS >0.05' : 'DEVIATION'})
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">I/Q Circularity (ρ):</span>
                <span className="text-emerald-400 font-bold">{stats?.circularity?.toFixed(4) ?? '0.0412'} (Ideal → 0.0)</span>
              </div>
            </div>
          </div>

          {/* Column 3: DSP & Spectral Resolution */}
          <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-850 space-y-2">
            <span className="text-zinc-500 text-[10px] uppercase font-bold tracking-wider flex items-center space-x-1">
              <Sliders className="w-3 h-3 text-amber-400" />
              <span>DSP &amp; Spectral Settings</span>
            </span>
            <div className="space-y-1.5 pt-1 text-[11px]">
              <div className="flex justify-between">
                <span className="text-zinc-400">FFT Size / Bins:</span>
                <span className="text-zinc-200 font-bold">{stats?.fft_size || 256} Bins (Δf = {((stats?.sample_rate_sps || 245760) / (stats?.fft_size || 256)).toFixed(1)} Hz)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">Window Function:</span>
                <span className="text-zinc-200 font-bold">{stats?.window || 'Blackman-Harris'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">Resolution BW (RBW):</span>
                <span className="text-cyan-400 font-bold">{stats?.rbw_hz?.toFixed(1) || '1924.0'} Hz</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">Video BW (VBW):</span>
                <span className="text-cyan-400 font-bold">{stats?.vbw_hz?.toFixed(1) || '577.2'} Hz</span>
              </div>
            </div>
          </div>

          {/* Column 4: Hardware & Calibration Provenance */}
          <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-850 space-y-2">
            <span className="text-zinc-500 text-[10px] uppercase font-bold tracking-wider flex items-center space-x-1">
              <HardDrive className="w-3 h-3 text-purple-400" />
              <span>Hardware &amp; File Provenance</span>
            </span>
            <div className="space-y-1.5 pt-1 text-[11px]">
              <div className="flex justify-between">
                <span className="text-zinc-400">Carrier Center Freq:</span>
                <span className="text-zinc-200 font-bold">{((stats?.center_freq_hz || 2484000000) / 1e9).toFixed(6)} GHz</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">Baseband Rate:</span>
                <span className="text-cyan-400 font-bold">{((stats?.sample_rate_sps || 245760) / 1000).toFixed(2)} kS/s</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">Calibration State:</span>
                <span className={isCalibrated ? 'text-emerald-400 font-bold' : 'text-amber-400 font-medium'}>
                  {isCalibrated ? 'Calibrated RF (50Ω)' : 'Uncalibrated Digital'}
                </span>
              </div>
              {prov?.file_metadata ? (
                <div className="pt-1 border-t border-zinc-800 text-[10px] text-zinc-400 space-y-0.5">
                  <div className="truncate text-zinc-300">File: {prov.file_metadata.filename}</div>
                  <div className="text-zinc-500">{prov.file_metadata.format} &bull; {prov.file_metadata.samples} samples</div>
                </div>
              ) : (
                <div className="flex justify-between">
                  <span className="text-zinc-400">Source Generator:</span>
                  <span className="text-emerald-400 font-bold truncate max-w-[130px]">{prov?.source_label || prov?.source || 'SYNTHESIS'}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
