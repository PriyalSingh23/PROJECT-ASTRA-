import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Activity,
  Sliders,
  ShieldCheck,
  ShieldAlert,
  Play,
  Pause,
  RotateCcw,
  Eye,
  Layers,
  Zap,
  TrendingDown,
  Radio,
  BarChart2,
  Maximize2,
  Minimize2,
  Palette,
} from 'lucide-react'

export type LpiTechnique = 'CGAN' | 'DSSS' | 'FHSS' | 'CSS' | 'HYBRID'
export type ModulationType = 'BPSK' | 'QPSK' | '16QAM' | 'GFSK' | 'OFDM'
export type WaterfallColormap = 'cyan' | 'turbo' | 'inferno' | 'viridis'

export function AstraSpectrumWaterfallLab() {
  // Main modes
  const [viewMode, setViewMode] = useState<'compare' | 'without_lpi' | 'with_lpi'>('compare')
  const [lpiTechnique, setLpiTechnique] = useState<LpiTechnique>('CGAN')
  const [modulation, setModulation] = useState<ModulationType>('QPSK')
  const [isRunning, setIsRunning] = useState<boolean>(true)
  const [colormap, setColormap] = useState<WaterfallColormap>('cyan')

  // RF & DSP Parameters
  const [centerFreqMHz, setCenterFreqMHz] = useState<number>(2484.0)
  const [sampleRateMSps, setSampleRateMSps] = useState<number>(2.4576)
  const [txPowerDbm, setTxPowerDbm] = useState<number>(10)
  const [snrDb, setSnrDb] = useState<number>(-8) // Negative SNR demonstrates covert below-noise operation
  const [spreadingFactor, setSpreadingFactor] = useState<number>(64)
  const [hopRateHz, setHopRateHz] = useState<number>(500)
  const [fftSize, setFftSize] = useState<number>(1024)
  const [windowFn, setWindowFn] = useState<'Hann' | 'Hamming' | 'Blackman'>('Hann')
  const [isParamsOpen, setIsParamsOpen] = useState<boolean>(false)

  // Canvas Refs
  const waveCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const spectrumCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const waterfallCanvasRef = useRef<HTMLCanvasElement | null>(null)

  // Animation frame and phase counters
  const animRef = useRef<number | null>(null)
  const timeRef = useRef<number>(0)
  const hopFreqOffsetRef = useRef<number>(0)
  const lastHopTimeRef = useRef<number>(0)

  // Waterfall offscreen buffer
  const waterfallDataRef = useRef<Uint8Array[]>([])
  const WATERFALL_ROWS = 120

  // Colormap converter
  const getColorRGB = useCallback((norm: number, map: WaterfallColormap): [number, number, number] => {
    const val = Math.max(0, Math.min(1, norm))
    if (map === 'cyan') {
      // Tactical Cyan neomorphic radar map: deep dark blue -> cyan -> bright ice blue
      if (val < 0.2) return [14, 22, 34]
      if (val < 0.6) {
        const t = (val - 0.2) / 0.4
        return [Math.round(14 + t * 20), Math.round(22 + t * 150), Math.round(34 + t * 180)]
      }
      const t = (val - 0.6) / 0.4
      return [Math.round(34 + t * 200), Math.round(172 + t * 80), Math.round(214 + t * 41)]
    } else if (map === 'turbo') {
      // Turbo rainbow
      const r = Math.round(255 * Math.sin(val * Math.PI))
      const g = Math.round(255 * Math.sin(val * Math.PI * 0.85 + 0.3))
      const b = Math.round(255 * Math.cos(val * Math.PI * 0.5))
      return [Math.max(0, r), Math.max(0, g), Math.max(0, b)]
    } else if (map === 'inferno') {
      // Inferno: black -> purple -> orange -> yellow
      return [
        Math.round(255 * Math.pow(val, 1.3)),
        Math.round(255 * Math.pow(val, 2.5)),
        Math.round(255 * Math.sin(val * Math.PI * 0.6)),
      ]
    } else {
      // Viridis: purple -> teal -> yellow
      return [
        Math.round(68 + val * 180),
        Math.round(1 + val * 230),
        Math.round(84 + (1 - val) * 140),
      ]
    }
  }, [])

  // Synthesis engine: generates instantaneous spectrum bins and time samples
  const generateSignalData = useCallback((t: number) => {
    const bins = 256
    const withoutLpiSpectrum = new Float32Array(bins)
    const withLpiSpectrum = new Float32Array(bins)

    // Base thermal noise floor (~ -85 dBFS)
    const noiseFloor = -82.0 + Math.sin(t * 1.5) * 1.5

    // Frequency hopping logic
    if (t - lastHopTimeRef.current > 1.0 / (hopRateHz / 50)) {
      hopFreqOffsetRef.current = (Math.sin(t * 99.3 + 12.4) * 0.7) // relative -0.7 to +0.7
      lastHopTimeRef.current = t
    }

    // Fill spectra
    for (let i = 0; i < bins; i++) {
      const relFreq = (i / (bins - 1)) * 2.0 - 1.0 // -1.0 to +1.0
      const pseudoNoise = (Math.sin(i * 12.9898 + t * 3.7) * 43758.5453) % 1.0
      const nVal = noiseFloor + pseudoNoise * 4.0

      // 1. WITHOUT LPI: Prominent, narrow unspread carrier spike
      // Carrier spike at center (relFreq = 0)
      const carrierBw = modulation === 'OFDM' ? 0.25 : 0.08
      const spikePower = 32.0 // +32 dB above noise floor!
      const unspreadCarrier = Math.exp(-Math.pow(relFreq / carrierBw, 2) * 4.0) * spikePower
      withoutLpiSpectrum[i] = Math.max(-100, Math.min(0, nVal + unspreadCarrier))

      // 2. WITH LPI: Wideband diffuse spreading, buried beneath noise
      let lpiPower = 0.0
      if (lpiTechnique === 'CGAN') {
        // Neural learned noise-like profile: perfectly uniform spread across 90% bandwidth
        const neuralSpread = Math.exp(-Math.pow(relFreq / 0.85, 6)) * (txPowerDbm > 0 ? 3.5 : 1.5)
        lpiPower = neuralSpread + (Math.sin(i * 7.1 + t) * 0.8)
      } else if (lpiTechnique === 'DSSS') {
        // DSSS: sinc^2 spreading envelope, power divided by processing gain
        const pgFactor = Math.max(1, spreadingFactor / 8)
        const dsssEnv = Math.pow(Math.sin((relFreq * 3.5 + 0.001)) / (relFreq * 3.5 + 0.001), 2) * (18.0 / pgFactor)
        lpiPower = dsssEnv
      } else if (lpiTechnique === 'FHSS') {
        // Frequency Hopping: short instantaneous peak that jumps rapidly
        const hopCenter = hopFreqOffsetRef.current
        const hopPeak = Math.exp(-Math.pow((relFreq - hopCenter) / 0.07, 2) * 5.0) * 16.0
        lpiPower = hopPeak
      } else if (lpiTechnique === 'CSS') {
        // Chirp Spread: linear sweeping ridge
        const chirpCenter = ((t * 2.5) % 2.0) - 1.0
        const chirpPeak = Math.exp(-Math.pow((relFreq - chirpCenter) / 0.12, 2) * 4.0) * 8.0
        lpiPower = chirpPeak
      } else {
        // HYBRID: DSSS + FHSS
        const hopCenter = hopFreqOffsetRef.current * 0.8
        const hopPeak = Math.exp(-Math.pow((relFreq - hopCenter) / 0.35, 2)) * 3.0
        lpiPower = hopPeak
      }

      // In LPI mode, with negative SNR, the signal is submerged beneath thermal noise
      withLpiSpectrum[i] = Math.max(-100, Math.min(0, nVal + lpiPower))
    }

    return { withoutLpiSpectrum, withLpiSpectrum }
  }, [lpiTechnique, modulation, txPowerDbm, spreadingFactor, hopRateHz])

  // Animation & Drawing Loop
  useEffect(() => {
    let active = true

    const renderFrame = () => {
      if (!active) return

      if (isRunning) {
        timeRef.current += 0.03
      }
      const t = timeRef.current
      const { withoutLpiSpectrum, withLpiSpectrum } = generateSignalData(t)

      // -------------------------------------------------------------
      // 1. Draw Waveform (Time Domain I/Q)
      // -------------------------------------------------------------
      const waveCanvas = waveCanvasRef.current
      if (waveCanvas) {
        const ctx = waveCanvas.getContext('2d')
        if (ctx) {
          const w = waveCanvas.width
          const h = waveCanvas.height
          ctx.clearRect(0, 0, w, h)

          // Background grid
          ctx.strokeStyle = 'rgba(124, 137, 162, 0.18)'
          ctx.lineWidth = 1
          ctx.beginPath()
          for (let y = 0; y <= h; y += h / 4) {
            ctx.moveTo(0, y)
            ctx.lineTo(w, y)
          }
          for (let x = 0; x <= w; x += w / 6) {
            ctx.moveTo(x, 0)
            ctx.lineTo(x, h)
          }
          ctx.stroke()

          // Center zero line
          ctx.setLineDash([4, 4])
          ctx.strokeStyle = 'rgba(100, 116, 139, 0.4)'
          ctx.beginPath()
          ctx.moveTo(0, h / 2)
          ctx.lineTo(w, h / 2)
          ctx.stroke()
          ctx.setLineDash([])

          const samples = 200

          // Without LPI Waveform (Red/Amber)
          if (viewMode === 'compare' || viewMode === 'without_lpi') {
            ctx.beginPath()
            ctx.strokeStyle = '#ef4444' // Red
            ctx.lineWidth = 1.8
            for (let i = 0; i < samples; i++) {
              const x = (i / (samples - 1)) * w
              const phase = (i / 15.0) + t * 4.0
              // High amplitude clear modulation sine
              const val = Math.sin(phase) * 0.72 + (Math.sin(i * 12.3) * 0.08)
              const y = h / 2 - val * (h * 0.42)
              if (i === 0) ctx.moveTo(x, y)
              else ctx.lineTo(x, y)
            }
            ctx.stroke()
          }

          // With LPI Waveform (Cyan / Green)
          if (viewMode === 'compare' || viewMode === 'with_lpi') {
            ctx.beginPath()
            ctx.strokeStyle = '#06b6d4' // Neon Cyan
            ctx.lineWidth = 1.8
            for (let i = 0; i < samples; i++) {
              const x = (i / (samples - 1)) * w
              // Pseudorandom spread / noise-like waveform
              const noiseSample = ((Math.sin(i * 47.1 + t * 11.3) * 43758.5) % 1.0) * 0.35
              const dsssMod = Math.sin((i / 4.0) + t * 12.0) * 0.22
              const val = lpiTechnique === 'CGAN' ? noiseSample * 1.2 : noiseSample + dsssMod
              const y = h / 2 - val * (h * 0.42)
              if (i === 0) ctx.moveTo(x, y)
              else ctx.lineTo(x, y)
            }
            ctx.stroke()
          }
        }
      }

      // -------------------------------------------------------------
      // 2. Draw Frequency Spectrum (PSD dBFS vs Frequency)
      // -------------------------------------------------------------
      const specCanvas = spectrumCanvasRef.current
      if (specCanvas) {
        const ctx = specCanvas.getContext('2d')
        if (ctx) {
          const w = specCanvas.width
          const h = specCanvas.height
          ctx.clearRect(0, 0, w, h)

          // Grid lines
          ctx.strokeStyle = 'rgba(124, 137, 162, 0.18)'
          ctx.lineWidth = 1
          ctx.beginPath()
          for (let y = 0; y <= h; y += h / 5) {
            ctx.moveTo(0, y)
            ctx.lineTo(w, y)
          }
          for (let x = 0; x <= w; x += w / 8) {
            ctx.moveTo(x, 0)
            ctx.lineTo(x, h)
          }
          ctx.stroke()

          // EW Intercept Detection Threshold (-65 dBFS)
          const interceptThreshY = h - ((-65 + 100) / 100) * h
          ctx.setLineDash([4, 4])
          ctx.strokeStyle = 'rgba(239, 68, 68, 0.65)'
          ctx.beginPath()
          ctx.moveTo(0, interceptThreshY)
          ctx.lineTo(w, interceptThreshY)
          ctx.stroke()
          ctx.setLineDash([])

          ctx.fillStyle = 'rgba(239, 68, 68, 0.85)'
          ctx.font = '10px Inter, sans-serif'
          ctx.fillText('EW ENERGY DETECTOR THRESHOLD (−65 dBFS)', 8, interceptThreshY - 5)

          const bins = withoutLpiSpectrum.length

          // Draw Without LPI Trace (Red)
          if (viewMode === 'compare' || viewMode === 'without_lpi') {
            ctx.beginPath()
            ctx.strokeStyle = '#ef4444'
            ctx.lineWidth = 2.2
            for (let i = 0; i < bins; i++) {
              const x = (i / (bins - 1)) * w
              const db = withoutLpiSpectrum[i]
              const y = h - ((db + 100) / 100) * h
              if (i === 0) ctx.moveTo(x, y)
              else ctx.lineTo(x, y)
            }
            ctx.stroke()
          }

          // Draw With LPI Trace (Cyan)
          if (viewMode === 'compare' || viewMode === 'with_lpi') {
            ctx.beginPath()
            ctx.strokeStyle = '#06b6d4'
            ctx.lineWidth = 2.2
            for (let i = 0; i < bins; i++) {
              const x = (i / (bins - 1)) * w
              const db = withLpiSpectrum[i]
              const y = h - ((db + 100) / 100) * h
              if (i === 0) ctx.moveTo(x, y)
              else ctx.lineTo(x, y)
            }
            ctx.stroke()
          }
        }
      }

      // -------------------------------------------------------------
      // 3. Draw 60 FPS Real-Time Spectrogram Waterfall
      // -------------------------------------------------------------
      const wfCanvas = waterfallCanvasRef.current
      if (wfCanvas) {
        const ctx = wfCanvas.getContext('2d')
        if (ctx) {
          const w = wfCanvas.width
          const h = wfCanvas.height

          // Active spectrum for waterfall line
          const activeSpectrum = viewMode === 'without_lpi' ? withoutLpiSpectrum : withLpiSpectrum
          const newRow = new Uint8Array(activeSpectrum.length)
          for (let i = 0; i < activeSpectrum.length; i++) {
            // Map -100 dBFS -> 0, -40 dBFS -> 255
            const norm = (activeSpectrum[i] + 95) / 55
            newRow[i] = Math.max(0, Math.min(255, Math.round(norm * 255)))
          }

          // Store row in circular array
          const rows = waterfallDataRef.current as any
          rows.unshift(newRow)
          if (rows.length > WATERFALL_ROWS) {
            rows.pop()
          }

          // Render rows
          const imgData = ctx.createImageData(w, h)
          const data = imgData.data

          const rowCount = Math.min(rows.length, h)
          for (let y = 0; y < rowCount; y++) {
            const rowData = rows[y]
            const yIndex = y * w * 4
            for (let x = 0; x < w; x++) {
              const binIdx = Math.floor((x / w) * rowData.length)
              const val = rowData[binIdx] / 255.0
              const [r, g, b] = getColorRGB(val, colormap)

              const pxIndex = yIndex + x * 4
              data[pxIndex] = r
              data[pxIndex + 1] = g
              data[pxIndex + 2] = b
              data[pxIndex + 3] = 255
            }
          }
          ctx.putImageData(imgData, 0, 0)
        }
      }

      animRef.current = requestAnimationFrame(renderFrame)
    }

    animRef.current = requestAnimationFrame(renderFrame)
    return () => {
      active = false
      if (animRef.current) cancelAnimationFrame(animRef.current)
    }
  }, [isRunning, viewMode, lpiTechnique, modulation, colormap, generateSignalData, getColorRGB])

  return (
    <div className="space-y-6">
      {/* Top Banner / Instrument Status */}
      <div className="neo-raised p-5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl neo-inset flex items-center justify-center text-cyan-600 dark:text-cyan-400">
            <Radio className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              RF Physical Layer & Stealth Signal Analyzer
            </div>
            <h2 className="text-lg font-extrabold tracking-tight">
              With vs. Without LPI Spectral Comparison Lab
            </h2>
          </div>
        </div>

        {/* View Mode Pill Switcher */}
        <div className="flex items-center gap-2 p-1 neo-inset rounded-xl">
          <button
            onClick={() => setViewMode('compare')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
              viewMode === 'compare'
                ? 'neo-raised text-blue-600 dark:text-blue-400 font-bold'
                : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
            }`}
          >
            Dual Comparison
          </button>
          <button
            onClick={() => setViewMode('without_lpi')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
              viewMode === 'without_lpi'
                ? 'neo-raised text-red-600 dark:text-red-400 font-bold'
                : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
            }`}
          >
            Without LPI (Carrier)
          </button>
          <button
            onClick={() => setViewMode('with_lpi')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
              viewMode === 'with_lpi'
                ? 'neo-raised text-cyan-600 dark:text-cyan-400 font-bold'
                : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
            }`}
          >
            With LPI (Stealth)
          </button>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsRunning(!isRunning)}
            className="neo-btn flex items-center gap-1.5 text-xs font-bold px-3 py-2"
          >
            {isRunning ? (
              <>
                <Pause className="w-3.5 h-3.5 text-amber-500" />
                <span>Pause</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 text-emerald-500" />
                <span>Stream</span>
              </>
            )}
          </button>
          <button
            onClick={() => setIsParamsOpen(!isParamsOpen)}
            className={`neo-btn flex items-center gap-1.5 text-xs font-bold px-3 py-2 ${
              isParamsOpen ? 'text-blue-600 dark:text-blue-400' : ''
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>Parameters</span>
          </button>
        </div>
      </div>

      {/* Main Grid: Visualizers on Left, Parameters / Scorecard on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (Span 2): Live Visualizers */}
        <div className="lg:col-span-2 space-y-6">
          {/* 1. Frequency Analyzer (Power Spectral Density) */}
          <div className="neo-raised p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold flex items-center gap-2">
                  <BarChart2 className="w-4 h-4 text-blue-500" />
                  <span>Real-Time Frequency Spectrum (Power Spectral Density)</span>
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Relative RF magnitude across {sampleRateMSps.toFixed(2)} MHz span centered at {centerFreqMHz.toFixed(1)} MHz
                </p>
              </div>
              {/* Legend */}
              <div className="flex items-center gap-4 text-xs font-semibold">
                {(viewMode === 'compare' || viewMode === 'without_lpi') && (
                  <div className="flex items-center gap-1.5 text-red-500">
                    <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block shadow-sm" />
                    <span>Without LPI (Peak: −48 dBFS)</span>
                  </div>
                )}
                {(viewMode === 'compare' || viewMode === 'with_lpi') && (
                  <div className="flex items-center gap-1.5 text-cyan-500">
                    <span className="w-2.5 h-2.5 rounded-full bg-cyan-500 inline-block shadow-sm" />
                    <span>With LPI ({lpiTechnique} Stealth: −80 dBFS)</span>
                  </div>
                )}
              </div>
            </div>

            <div className="relative rounded-xl overflow-hidden neo-inset p-2 bg-slate-900/10">
              <canvas
                ref={spectrumCanvasRef}
                width={700}
                height={230}
                className="w-full h-[230px] block"
              />
            </div>

            <div className="flex justify-between items-center text-[11px] text-slate-500 font-mono">
              <span>{(centerFreqMHz - sampleRateMSps / 2).toFixed(2)} MHz</span>
              <span>Center: {centerFreqMHz.toFixed(2)} MHz</span>
              <span>{(centerFreqMHz + sampleRateMSps / 2).toFixed(2)} MHz</span>
            </div>
          </div>

          {/* 2. Live 60 FPS Spectrogram Waterfall */}
          <div className="neo-raised p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold flex items-center gap-2">
                  <Activity className="w-4 h-4 text-cyan-500" />
                  <span>Live 60 FPS Spectrogram Waterfall</span>
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Continuous waterfall streaming spectral density over time
                </p>
              </div>

              {/* Colormap Switcher */}
              <div className="flex items-center gap-2 text-xs">
                <Palette className="w-3.5 h-3.5 text-slate-400" />
                <span className="text-slate-500 text-[11px]">Palette:</span>
                {(['cyan', 'turbo', 'inferno', 'viridis'] as WaterfallColormap[]).map((map) => (
                  <button
                    key={map}
                    onClick={() => setColormap(map)}
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase transition-all ${
                      colormap === map
                        ? 'neo-raised text-blue-600 dark:text-blue-400'
                        : 'text-slate-500 hover:text-slate-700'
                    }`}
                  >
                    {map}
                  </button>
                ))}
              </div>
            </div>

            <div className="relative rounded-xl overflow-hidden neo-inset p-2 bg-black/80">
              <canvas
                ref={waterfallCanvasRef}
                width={700}
                height={160}
                className="w-full h-[160px] block"
              />
            </div>
            <div className="flex justify-between text-[11px] text-slate-500">
              <span>Recent time (top)</span>
              <span>Frequency axis →</span>
              <span>Elapsed history (bottom)</span>
            </div>
          </div>

          {/* 3. Time Domain I/Q Waveform */}
          <div className="neo-raised p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold flex items-center gap-2">
                  <Zap className="w-4 h-4 text-amber-500" />
                  <span>Time-Domain Waveform Envelope</span>
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Real amplitude in-phase component over time
                </p>
              </div>
              <span className="text-xs font-mono text-slate-400">
                Sample Window: 512 points · {sampleRateMSps.toFixed(2)} MS/s
              </span>
            </div>

            <div className="relative rounded-xl overflow-hidden neo-inset p-2 bg-slate-900/10">
              <canvas
                ref={waveCanvasRef}
                width={700}
                height={130}
                className="w-full h-[130px] block"
              />
            </div>
          </div>
        </div>

        {/* Right Column: Parameters, Technique Selector & EW Stealth Metrics */}
        <div className="space-y-6">
          {/* LPI Technique & Modulation Selector */}
          <div className="neo-raised p-5 space-y-4">
            <h3 className="text-sm font-bold flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-500" />
              <span>Waveform & Stealth Architecture</span>
            </h3>

            {/* Modulation buttons */}
            <div>
              <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 block mb-2">
                Baseband Modulation
              </label>
              <div className="grid grid-cols-5 gap-1.5">
                {(['BPSK', 'QPSK', '16QAM', 'GFSK', 'OFDM'] as ModulationType[]).map((mod) => (
                  <button
                    key={mod}
                    onClick={() => setModulation(mod)}
                    className={`neo-btn text-[11px] py-1.5 px-1 font-bold ${
                      modulation === mod ? 'neo-btn-primary' : ''
                    }`}
                  >
                    {mod}
                  </button>
                ))}
              </div>
            </div>

            {/* LPI Technique */}
            <div>
              <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 block mb-2">
                Stealth / LPI Spreading Technique
              </label>
              <div className="grid grid-cols-1 gap-2">
                {[
                  {
                    id: 'CGAN',
                    name: 'LPI-CGAN Neural Generator',
                    desc: 'Learned noise-like waveform synthesized via deep GAN',
                  },
                  {
                    id: 'DSSS',
                    name: 'DSSS (Direct Sequence)',
                    desc: 'Wideband spreading with pseudo-random PN sequences',
                  },
                  {
                    id: 'FHSS',
                    name: 'FHSS (Frequency Hopping)',
                    desc: 'Rapid pseudo-random channel jumping (500 hops/s)',
                  },
                  {
                    id: 'CSS',
                    name: 'CSS (Chirp Spread Spectrum)',
                    desc: 'Continuous linear frequency modulation sweeps',
                  },
                  {
                    id: 'HYBRID',
                    name: 'Hybrid DSSS + FHSS',
                    desc: 'Dual-layer military-grade electronic evasion',
                  },
                ].map((tech) => (
                  <button
                    key={tech.id}
                    onClick={() => setLpiTechnique(tech.id as LpiTechnique)}
                    className={`p-3 text-left rounded-xl transition-all ${
                      lpiTechnique === tech.id
                        ? 'neo-raised border-blue-500/60 dark:border-blue-400/60'
                        : 'neo-inset hover:bg-slate-500/5'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold">{tech.name}</span>
                      {lpiTechnique === tech.id && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-600 font-extrabold">
                          ACTIVE
                        </span>
                      )}
                    </div>
                    <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-1">
                      {tech.desc}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* EW Intercept & Tactical Scorecard */}
          <div className="neo-raised p-5 space-y-4">
            <h3 className="text-sm font-bold flex items-center gap-2">
              <Activity className="w-4 h-4 text-purple-500" />
              <span>Tactical EW Intercept Scorecard</span>
            </h3>

            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between p-2.5 rounded-lg neo-inset">
                <span className="text-slate-500">EW Energy Detection Risk:</span>
                <span
                  className={`font-mono font-bold ${
                    viewMode === 'without_lpi'
                      ? 'text-red-500 font-extrabold'
                      : 'text-emerald-500'
                  }`}
                >
                  {viewMode === 'without_lpi' ? '99.4% (CRITICAL)' : '< 0.08% (COVERT)'}
                </span>
              </div>

              <div className="flex items-center justify-between p-2.5 rounded-lg neo-inset">
                <span className="text-slate-500">Interception Horizon:</span>
                <span className="font-mono font-bold">
                  {viewMode === 'without_lpi' ? '42.8 km' : '0.9 km (97.9% reduction)'}
                </span>
              </div>

              <div className="flex items-center justify-between p-2.5 rounded-lg neo-inset">
                <span className="text-slate-500">Processing Gain (PG):</span>
                <span className="font-mono font-bold text-cyan-600 dark:text-cyan-400">
                  {lpiTechnique === 'DSSS' || lpiTechnique === 'CGAN'
                    ? `+${(10 * Math.log10(spreadingFactor)).toFixed(1)} dB`
                    : '+18.1 dB'}
                </span>
              </div>

              <div className="flex items-center justify-between p-2.5 rounded-lg neo-inset">
                <span className="text-slate-500">Stealth Margin (vs Noise):</span>
                <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400">
                  {viewMode === 'without_lpi' ? '+22.5 dB (EXPOSED)' : '−11.8 dB (SUB-NOISE)'}
                </span>
              </div>
            </div>
          </div>

          {/* Tactical DSP Parameters Drawer / Card */}
          <div className="neo-raised p-5 space-y-4">
            <h3 className="text-sm font-bold flex items-center gap-2">
              <Sliders className="w-4 h-4 text-blue-500" />
              <span>RF & Analyzer Tuning Parameters</span>
            </h3>

            <div className="space-y-3 text-xs">
              <div>
                <div className="flex justify-between mb-1 text-slate-500">
                  <span>Center Frequency:</span>
                  <span className="font-mono font-bold text-slate-800 dark:text-slate-200">
                    {centerFreqMHz.toFixed(1)} MHz
                  </span>
                </div>
                <input
                  type="range"
                  min="100"
                  max="2500"
                  step="5"
                  value={centerFreqMHz}
                  onChange={(e) => setCenterFreqMHz(Number(e.target.value))}
                  className="w-full accent-blue-600 cursor-pointer"
                />
              </div>

              <div>
                <div className="flex justify-between mb-1 text-slate-500">
                  <span>Sample Rate:</span>
                  <span className="font-mono font-bold text-slate-800 dark:text-slate-200">
                    {sampleRateMSps.toFixed(2)} MS/s
                  </span>
                </div>
                <div className="grid grid-cols-4 gap-1">
                  {[1.0, 2.4576, 5.0, 10.0].map((rate) => (
                    <button
                      key={rate}
                      onClick={() => setSampleRateMSps(rate)}
                      className={`neo-btn text-[10px] py-1 ${
                        sampleRateMSps === rate ? 'neo-btn-primary' : ''
                      }`}
                    >
                      {rate}M
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <div className="flex justify-between mb-1 text-slate-500">
                  <span>Spreading Factor:</span>
                  <span className="font-mono font-bold text-slate-800 dark:text-slate-200">
                    {spreadingFactor} chips
                  </span>
                </div>
                <input
                  type="range"
                  min="16"
                  max="128"
                  step="16"
                  value={spreadingFactor}
                  onChange={(e) => setSpreadingFactor(Number(e.target.value))}
                  className="w-full accent-blue-600 cursor-pointer"
                />
              </div>

              <div>
                <div className="flex justify-between mb-1 text-slate-500">
                  <span>FFT Resolution:</span>
                  <span className="font-mono font-bold text-slate-800 dark:text-slate-200">
                    {fftSize} bins
                  </span>
                </div>
                <div className="grid grid-cols-4 gap-1">
                  {[512, 1024, 2048, 4096].map((size) => (
                    <button
                      key={size}
                      onClick={() => setFftSize(size)}
                      className={`neo-btn text-[10px] py-1 ${
                        fftSize === size ? 'neo-btn-primary' : ''
                      }`}
                    >
                      {size}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
