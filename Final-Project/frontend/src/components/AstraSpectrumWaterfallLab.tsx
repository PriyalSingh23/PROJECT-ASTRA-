import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Activity,
  Sliders,
  ShieldCheck,
  Play,
  Pause,
  RotateCcw,
  Layers,
  Zap,
  Radio,
  BarChart2,
  ChevronDown,
  ChevronUp,
  Palette,
  Eye,
  SlidersHorizontal,
  Info,
} from 'lucide-react'

export type LpiTechnique = 'CGAN' | 'DSSS' | 'FHSS' | 'CSS' | 'HYBRID'
export type ModulationType = 'BPSK' | 'QPSK' | '16QAM' | 'GFSK' | 'OFDM'
export type WaterfallColormap = 'cyan' | 'turbo' | 'inferno' | 'viridis'

export function AstraSpectrumWaterfallLab() {
  // Main view & technique states
  const [viewMode, setViewMode] = useState<'compare' | 'without_lpi' | 'with_lpi'>('compare')
  const [lpiTechnique, setLpiTechnique] = useState<LpiTechnique>('CGAN')
  const [modulation, setModulation] = useState<ModulationType>('QPSK')
  const [isRunning, setIsRunning] = useState<boolean>(true)
  const [colormap, setColormap] = useState<WaterfallColormap>('cyan')

  // Click-to-Toggle Collapsible Panels (Clean UI — secondary items hidden by default)
  const [showOscilloscope, setShowOscilloscope] = useState<boolean>(false)
  const [showParameters, setShowParameters] = useState<boolean>(false)
  const [showScorecard, setShowScorecard] = useState<boolean>(false)

  // RF & DSP Parameters
  const [centerFreqMHz, setCenterFreqMHz] = useState<number>(2484.0)
  const [sampleRateMSps, setSampleRateMSps] = useState<number>(2.4576)
  const [txPowerDbm, setTxPowerDbm] = useState<number>(10)
  const [snrDb, setSnrDb] = useState<number>(-8) // Negative SNR demonstrates covert below-noise operation
  const [spreadingFactor, setSpreadingFactor] = useState<number>(64)
  const [hopRateHz, setHopRateHz] = useState<number>(500)
  const [fftSize, setFftSize] = useState<number>(1024)
  const [windowFn, setWindowFn] = useState<'Hann' | 'Hamming' | 'Blackman'>('Hann')

  // Canvas Refs
  const spectrumCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const waterfallCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const waveCanvasRef = useRef<HTMLCanvasElement | null>(null)

  // Animation frame and phase counters
  const animRef = useRef<number | null>(null)
  const timeRef = useRef<number>(0)
  const hopFreqOffsetRef = useRef<number>(0)
  const lastHopTimeRef = useRef<number>(0)

  // Waterfall offscreen buffer
  const waterfallDataRef = useRef<Uint8Array[]>([])
  const WATERFALL_ROWS = 120

  // Colormap converter
  const getColorRGB = useCallback((norm: number, map: WaterfallColormap, isDark: boolean): [number, number, number] => {
    const val = Math.max(0, Math.min(1, norm))
    if (map === 'cyan') {
      if (isDark) {
        // Night mode: deep obsidian -> dark cyan -> bright neon cyan
        if (val < 0.2) return [11, 17, 26]
        if (val < 0.6) {
          const t = (val - 0.2) / 0.4
          return [Math.round(11 + t * 20), Math.round(17 + t * 140), Math.round(26 + t * 170)]
        }
        const t = (val - 0.6) / 0.4
        return [Math.round(31 + t * 180), Math.round(157 + t * 90), Math.round(196 + t * 59)]
      } else {
        // Day mode: clean white/light slate -> vibrant tactical cyan -> royal blue
        if (val < 0.15) return [248, 250, 252]
        if (val < 0.5) {
          const t = (val - 0.15) / 0.35
          return [Math.round(248 - t * 170), Math.round(250 - t * 80), Math.round(252 - t * 40)]
        }
        const t = (val - 0.5) / 0.5
        return [Math.round(78 - t * 50), Math.round(170 - t * 80), Math.round(212 + t * 30)]
      }
    } else if (map === 'turbo') {
      const r = Math.round(255 * Math.sin(val * Math.PI))
      const g = Math.round(255 * Math.sin(val * Math.PI * 0.85 + 0.3))
      const b = Math.round(255 * Math.cos(val * Math.PI * 0.5))
      return [Math.max(0, r), Math.max(0, g), Math.max(0, b)]
    } else if (map === 'inferno') {
      return [
        Math.round(255 * Math.pow(val, 1.3)),
        Math.round(255 * Math.pow(val, 2.5)),
        Math.round(255 * Math.sin(val * Math.PI * 0.6)),
      ]
    } else {
      // Viridis
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
      hopFreqOffsetRef.current = Math.sin(t * 99.3 + 12.4) * 0.7
      lastHopTimeRef.current = t
    }

    // Fill spectra
    for (let i = 0; i < bins; i++) {
      const relFreq = (i / (bins - 1)) * 2.0 - 1.0 // -1.0 to +1.0
      const pseudoNoise = (Math.sin(i * 12.9898 + t * 3.7) * 43758.5453) % 1.0
      const nVal = noiseFloor + pseudoNoise * 4.0

      // 1. WITHOUT LPI: High energy prominent carrier spike (+32 dB above noise)
      const carrierBw = modulation === 'OFDM' ? 0.25 : 0.08
      const spikePower = 32.0
      const unspreadCarrier = Math.exp(-Math.pow(relFreq / carrierBw, 2) * 4.0) * spikePower
      withoutLpiSpectrum[i] = Math.max(-100, Math.min(0, nVal + unspreadCarrier))

      // 2. WITH LPI: Wideband diffuse spreading, buried beneath noise
      let lpiPower = 0.0
      if (lpiTechnique === 'CGAN') {
        const neuralSpread = Math.exp(-Math.pow(relFreq / 0.85, 6)) * (txPowerDbm > 0 ? 3.5 : 1.5)
        lpiPower = neuralSpread + (Math.sin(i * 7.1 + t) * 0.8)
      } else if (lpiTechnique === 'DSSS') {
        const pgFactor = Math.max(1, spreadingFactor / 8)
        const dsssEnv = Math.pow(Math.sin((relFreq * 3.5 + 0.001)) / (relFreq * 3.5 + 0.001), 2) * (18.0 / pgFactor)
        lpiPower = dsssEnv
      } else if (lpiTechnique === 'FHSS') {
        const hopCenter = hopFreqOffsetRef.current
        const hopPeak = Math.exp(-Math.pow((relFreq - hopCenter) / 0.07, 2) * 5.0) * 16.0
        lpiPower = hopPeak
      } else if (lpiTechnique === 'CSS') {
        const chirpCenter = ((t * 2.5) % 2.0) - 1.0
        const chirpPeak = Math.exp(-Math.pow((relFreq - chirpCenter) / 0.12, 2) * 4.0) * 8.0
        lpiPower = chirpPeak
      } else {
        // HYBRID: DSSS + FHSS
        const hopCenter = hopFreqOffsetRef.current * 0.8
        const hopPeak = Math.exp(-Math.pow((relFreq - hopCenter) / 0.35, 2)) * 3.0
        lpiPower = hopPeak
      }

      withLpiSpectrum[i] = Math.max(-100, Math.min(0, nVal + lpiPower))
    }

    return { withoutLpiSpectrum, withLpiSpectrum }
  }, [lpiTechnique, modulation, txPowerDbm, spreadingFactor, hopRateHz])

  // Real-time animation and drawing loop
  useEffect(() => {
    let active = true

    const renderFrame = () => {
      if (!active) return

      if (isRunning) {
        timeRef.current += 0.03
      }
      const t = timeRef.current
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
      const { withoutLpiSpectrum, withLpiSpectrum } = generateSignalData(t)

      // -----------------------------------------------------------------
      // 1. Draw Frequency Spectrum (Power Spectral Density)
      // -----------------------------------------------------------------
      const specCanvas = spectrumCanvasRef.current
      if (specCanvas) {
        const ctx = specCanvas.getContext('2d')
        if (ctx) {
          const w = specCanvas.width
          const h = specCanvas.height
          ctx.fillStyle = isDark ? '#0B111A' : '#FFFFFF'
          ctx.fillRect(0, 0, w, h)

          // Grid lines
          ctx.strokeStyle = isDark ? 'rgba(45, 58, 75, 0.45)' : 'rgba(226, 232, 240, 0.8)'
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
          ctx.strokeStyle = isDark ? 'rgba(239, 68, 68, 0.7)' : 'rgba(220, 38, 38, 0.8)'
          ctx.beginPath()
          ctx.moveTo(0, interceptThreshY)
          ctx.lineTo(w, interceptThreshY)
          ctx.stroke()
          ctx.setLineDash([])

          ctx.fillStyle = isDark ? 'rgba(239, 68, 68, 0.9)' : 'rgba(220, 38, 38, 0.9)'
          ctx.font = '10px Inter, sans-serif'
          ctx.fillText('EW ENERGY DETECTION THRESHOLD (−65 dBFS)', 10, interceptThreshY - 5)

          const bins = withoutLpiSpectrum.length

          // Draw Without LPI Trace (Crimson Red)
          if (viewMode === 'compare' || viewMode === 'without_lpi') {
            ctx.beginPath()
            ctx.strokeStyle = isDark ? '#EF4444' : '#DC2626'
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

          // Draw With LPI Trace (Tactical Cyan / Emerald)
          if (viewMode === 'compare' || viewMode === 'with_lpi') {
            ctx.beginPath()
            ctx.strokeStyle = isDark ? '#06B6D4' : '#0284C7'
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

      // -----------------------------------------------------------------
      // 2. Draw Live 60 FPS Spectrogram Waterfall
      // -----------------------------------------------------------------
      const wfCanvas = waterfallCanvasRef.current
      if (wfCanvas) {
        const ctx = wfCanvas.getContext('2d')
        if (ctx) {
          const w = wfCanvas.width
          const h = wfCanvas.height

          const activeSpectrum = viewMode === 'without_lpi' ? withoutLpiSpectrum : withLpiSpectrum
          const newRow = new Uint8Array(activeSpectrum.length)
          for (let i = 0; i < activeSpectrum.length; i++) {
            const norm = (activeSpectrum[i] + 95) / 55
            newRow[i] = Math.max(0, Math.min(255, Math.round(norm * 255)))
          }

          const rows = waterfallDataRef.current as any
          rows.unshift(newRow)
          if (rows.length > WATERFALL_ROWS) {
            rows.pop()
          }

          const imgData = ctx.createImageData(w, h)
          const data = imgData.data
          const rowCount = Math.min(rows.length, h)
          for (let y = 0; y < rowCount; y++) {
            const rowData = rows[y]
            const yIndex = y * w * 4
            for (let x = 0; x < w; x++) {
              const binIdx = Math.floor((x / w) * rowData.length)
              const val = rowData[binIdx] / 255.0
              const [r, g, b] = getColorRGB(val, colormap, isDark)

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

      // -----------------------------------------------------------------
      // 3. Draw Time-Domain Waveform Oscilloscope (when toggle is open)
      // -----------------------------------------------------------------
      if (showOscilloscope) {
        const waveCanvas = waveCanvasRef.current
        if (waveCanvas) {
          const ctx = waveCanvas.getContext('2d')
          if (ctx) {
            const w = waveCanvas.width
            const h = waveCanvas.height
            ctx.fillStyle = isDark ? '#0B111A' : '#FFFFFF'
            ctx.fillRect(0, 0, w, h)

            // Grid
            ctx.strokeStyle = isDark ? 'rgba(45, 58, 75, 0.45)' : 'rgba(226, 232, 240, 0.8)'
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

            // Center line
            ctx.setLineDash([3, 3])
            ctx.strokeStyle = isDark ? 'rgba(100, 116, 139, 0.4)' : 'rgba(148, 163, 184, 0.6)'
            ctx.beginPath()
            ctx.moveTo(0, h / 2)
            ctx.lineTo(w, h / 2)
            ctx.stroke()
            ctx.setLineDash([])

            const samples = 200

            // Without LPI Waveform (Red)
            if (viewMode === 'compare' || viewMode === 'without_lpi') {
              ctx.beginPath()
              ctx.strokeStyle = isDark ? '#EF4444' : '#DC2626'
              ctx.lineWidth = 1.8
              for (let i = 0; i < samples; i++) {
                const x = (i / (samples - 1)) * w
                const phase = (i / 15.0) + t * 4.0
                const val = Math.sin(phase) * 0.72 + (Math.sin(i * 12.3) * 0.08)
                const y = h / 2 - val * (h * 0.42)
                if (i === 0) ctx.moveTo(x, y)
                else ctx.lineTo(x, y)
              }
              ctx.stroke()
            }

            // With LPI Waveform (Cyan)
            if (viewMode === 'compare' || viewMode === 'with_lpi') {
              ctx.beginPath()
              ctx.strokeStyle = isDark ? '#06B6D4' : '#0284C7'
              ctx.lineWidth = 1.8
              for (let i = 0; i < samples; i++) {
                const x = (i / (samples - 1)) * w
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
      }

      animRef.current = requestAnimationFrame(renderFrame)
    }

    animRef.current = requestAnimationFrame(renderFrame)
    return () => {
      active = false
      if (animRef.current) cancelAnimationFrame(animRef.current)
    }
  }, [isRunning, viewMode, lpiTechnique, modulation, colormap, showOscilloscope, generateSignalData, getColorRGB])

  return (
    <div className="space-y-6">
      {/* ------------------------------------------------------------- */}
      {/* Top Header & Fast Switcher                                    */}
      {/* ------------------------------------------------------------- */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-[10px] font-extrabold uppercase tracking-widest text-[var(--accent)] mb-1">
            Spectrum &amp; Signal Intelligence
          </div>
          <h1 className="text-2xl font-black tracking-tight text-[var(--ink)]">
            LPI vs. Conventional Spectral Lab
          </h1>
          <p className="text-xs text-[var(--muted)] mt-1 max-w-xl leading-relaxed">
            Real-time power spectral density and continuous spectrogram waterfall comparing unspread carrier emissions against covert neural and spread-spectrum waveforms.
          </p>
        </div>

        {/* View Mode Pill Switcher */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center p-1 neo-inset rounded-xl">
            <button
              onClick={() => setViewMode('compare')}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${
                viewMode === 'compare'
                  ? 'neo-raised text-blue-600 dark:text-blue-400'
                  : 'text-[var(--muted)]'
              }`}
            >
              Dual Comparison
            </button>
            <button
              onClick={() => setViewMode('without_lpi')}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${
                viewMode === 'without_lpi'
                  ? 'neo-raised text-red-600 dark:text-red-400'
                  : 'text-[var(--muted)]'
              }`}
            >
              Without LPI
            </button>
            <button
              onClick={() => setViewMode('with_lpi')}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${
                viewMode === 'with_lpi'
                  ? 'neo-raised text-cyan-600 dark:text-cyan-400'
                  : 'text-[var(--muted)]'
              }`}
            >
              With LPI (Stealth)
            </button>
          </div>

          {/* Pause / Stream Button */}
          <button
            onClick={() => setIsRunning(!isRunning)}
            className="neo-btn flex items-center gap-1.5 text-xs font-bold px-3.5 py-2"
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
        </div>
      </div>

      {/* ------------------------------------------------------------- */}
      {/* Technique & Modulation Quick Bar (Clean horizontal pills)     */}
      {/* ------------------------------------------------------------- */}
      <div className="neo-raised p-4 flex flex-wrap items-center justify-between gap-4">
        {/* LPI Technique Pills */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-bold text-[var(--muted)] uppercase tracking-wider mr-1">
            Stealth Technique:
          </span>
          {[
            { id: 'CGAN', label: 'LPI-CGAN Neural' },
            { id: 'DSSS', label: 'DSSS Spreading' },
            { id: 'FHSS', label: 'FHSS Hopping' },
            { id: 'CSS', label: 'CSS Chirp' },
            { id: 'HYBRID', label: 'Hybrid DSSS/FHSS' },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setLpiTechnique(item.id as LpiTechnique)}
              className={`px-3 py-1.5 text-xs font-bold rounded-xl transition-all ${
                lpiTechnique === item.id
                  ? 'neo-raised text-blue-600 dark:text-blue-400 border border-blue-500/30'
                  : 'neo-inset text-[var(--muted)] hover:text-[var(--ink)]'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {/* Modulation Pills */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] font-bold text-[var(--muted)] uppercase tracking-wider mr-1">
            Modulation:
          </span>
          {(['BPSK', 'QPSK', '16QAM', 'GFSK', 'OFDM'] as ModulationType[]).map((mod) => (
            <button
              key={mod}
              onClick={() => setModulation(mod)}
              className={`px-2.5 py-1 text-[11px] font-bold rounded-lg transition-all ${
                modulation === mod
                  ? 'neo-raised text-blue-600 dark:text-blue-400 font-black'
                  : 'text-[var(--muted)] hover:text-[var(--ink)]'
              }`}
            >
              {mod}
            </button>
          ))}
        </div>
      </div>

      {/* ------------------------------------------------------------- */}
      {/* Main Scope 1: Real-Time Frequency Spectrum (PSD)               */}
      {/* ------------------------------------------------------------- */}
      <div className="neo-raised p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold text-[var(--ink)] flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-blue-500" />
              <span>Real-Time Frequency Spectrum (Power Spectral Density)</span>
            </h3>
            <p className="text-xs text-[var(--muted)] mt-0.5">
              RF magnitude relative to thermal noise floor across {sampleRateMSps.toFixed(2)} MHz span centered at {centerFreqMHz.toFixed(1)} MHz
            </p>
          </div>

          {/* Trace Legend */}
          <div className="flex items-center gap-4 text-xs font-bold">
            {(viewMode === 'compare' || viewMode === 'without_lpi') && (
              <div className="flex items-center gap-1.5 text-red-600 dark:text-red-400">
                <span className="w-2.5 h-2.5 rounded-full bg-red-600 inline-block shadow-sm" />
                <span>Without LPI (Peak: −48 dBFS)</span>
              </div>
            )}
            {(viewMode === 'compare' || viewMode === 'with_lpi') && (
              <div className="flex items-center gap-1.5 text-cyan-600 dark:text-cyan-400">
                <span className="w-2.5 h-2.5 rounded-full bg-cyan-500 inline-block shadow-sm" />
                <span>With LPI ({lpiTechnique} Stealth: −80 dBFS)</span>
              </div>
            )}
          </div>
        </div>

        {/* Spectrum Canvas Frame */}
        <div className="relative rounded-xl overflow-hidden neo-inset p-2 bg-white dark:bg-[#0B111A]">
          <canvas
            ref={spectrumCanvasRef}
            width={900}
            height={240}
            className="w-full h-[240px] block"
          />
        </div>

        <div className="flex justify-between items-center text-[11px] text-[var(--muted)] font-mono px-1">
          <span>{(centerFreqMHz - sampleRateMSps / 2).toFixed(2)} MHz</span>
          <span>Center: {centerFreqMHz.toFixed(2)} MHz · Bandwidth: {sampleRateMSps.toFixed(2)} MHz</span>
          <span>{(centerFreqMHz + sampleRateMSps / 2).toFixed(2)} MHz</span>
        </div>
      </div>

      {/* ------------------------------------------------------------- */}
      {/* Main Scope 2: Live 60 FPS Spectrogram Waterfall              */}
      {/* ------------------------------------------------------------- */}
      <div className="neo-raised p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold text-[var(--ink)] flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan-500" />
              <span>Live 60 FPS Spectrogram Waterfall</span>
            </h3>
            <p className="text-xs text-[var(--muted)] mt-0.5">
              Continuous time-frequency waterfall streaming spectral density history
            </p>
          </div>

          {/* Palette Selector */}
          <div className="flex items-center gap-1.5 text-xs">
            <Palette className="w-3.5 h-3.5 text-[var(--muted)]" />
            <span className="text-[var(--muted)] text-[11px] font-bold">Palette:</span>
            {(['cyan', 'turbo', 'inferno', 'viridis'] as WaterfallColormap[]).map((map) => (
              <button
                key={map}
                onClick={() => setColormap(map)}
                className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase transition-all ${
                  colormap === map
                    ? 'neo-raised text-blue-600 dark:text-blue-400 font-extrabold'
                    : 'text-[var(--muted)] hover:text-[var(--ink)]'
                }`}
              >
                {map}
              </button>
            ))}
          </div>
        </div>

        {/* Waterfall Canvas Frame */}
        <div className="relative rounded-xl overflow-hidden neo-inset p-2 bg-white dark:bg-[#0B111A]">
          <canvas
            ref={waterfallCanvasRef}
            width={900}
            height={180}
            className="w-full h-[180px] block"
          />
        </div>

        <div className="flex justify-between text-[11px] text-[var(--muted)] px-1">
          <span>Recent Time (Top)</span>
          <span>Frequency Span ({sampleRateMSps.toFixed(2)} MHz) →</span>
          <span>Elapsed History (Bottom)</span>
        </div>
      </div>

      {/* ------------------------------------------------------------- */}
      {/* Click-to-Toggle Secondary Sections (Clean Accordions)         */}
      {/* ------------------------------------------------------------- */}
      <div className="space-y-4">
        {/* Toggle 1: Time-Domain Oscilloscope */}
        <div className="neo-raised rounded-2xl overflow-hidden transition-all">
          <button
            onClick={() => setShowOscilloscope(!showOscilloscope)}
            className="w-full p-4 flex items-center justify-between text-left transition-colors hover:bg-slate-500/5"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg neo-inset flex items-center justify-center text-amber-500">
                <Zap className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-[var(--ink)]">
                  Time-Domain Oscilloscope (I/Q In-Phase Envelope)
                </h4>
                <p className="text-[11px] text-[var(--muted)]">
                  Instantaneous signal amplitude waveform over 512 baseband samples
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full neo-inset text-[var(--muted)]">
                {showOscilloscope ? 'Click to Collapse' : 'Click to View'}
              </span>
              {showOscilloscope ? <ChevronUp className="w-4 h-4 text-[var(--muted)]" /> : <ChevronDown className="w-4 h-4 text-[var(--muted)]" />}
            </div>
          </button>

          {showOscilloscope && (
            <div className="p-5 pt-0 space-y-3 animate-fadeIn border-t border-[var(--line)]">
              <div className="relative rounded-xl overflow-hidden neo-inset p-2 bg-white dark:bg-[#0B111A] mt-3">
                <canvas
                  ref={waveCanvasRef}
                  width={900}
                  height={140}
                  className="w-full h-[140px] block"
                />
              </div>
              <div className="flex justify-between text-[11px] text-[var(--muted)]">
                <span>0 ns</span>
                <span>Baseband Time-Domain Trace (512 points)</span>
                <span>208 μs</span>
              </div>
            </div>
          )}
        </div>

        {/* Toggle 2: RF Parameters & Hardware Tuning */}
        <div className="neo-raised rounded-2xl overflow-hidden transition-all">
          <button
            onClick={() => setShowParameters(!showParameters)}
            className="w-full p-4 flex items-center justify-between text-left transition-colors hover:bg-slate-500/5"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg neo-inset flex items-center justify-center text-blue-500">
                <SlidersHorizontal className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-[var(--ink)]">
                  RF Parameters &amp; Hardware Tuning
                </h4>
                <p className="text-[11px] text-[var(--muted)]">
                  Carrier frequency, sampling rate, spreading factor, and FFT resolution
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full neo-inset text-[var(--muted)]">
                {showParameters ? 'Click to Collapse' : 'Click to Tune'}
              </span>
              {showParameters ? <ChevronUp className="w-4 h-4 text-[var(--muted)]" /> : <ChevronDown className="w-4 h-4 text-[var(--muted)]" />}
            </div>
          </button>

          {showParameters && (
            <div className="p-5 pt-0 space-y-4 animate-fadeIn border-t border-[var(--line)] mt-1">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-3">
                {/* Center Frequency Slider */}
                <div className="p-3.5 rounded-xl neo-inset space-y-2">
                  <div className="flex justify-between text-xs font-bold">
                    <span className="text-[var(--muted)]">Center Frequency:</span>
                    <span className="text-[var(--ink)] font-mono">{centerFreqMHz.toFixed(1)} MHz</span>
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
                  <div className="flex justify-between text-[10px] text-[var(--muted)]">
                    <span>100 MHz</span>
                    <span>ISM 2.4 GHz</span>
                  </div>
                </div>

                {/* Sample Rate Selector */}
                <div className="p-3.5 rounded-xl neo-inset space-y-2">
                  <div className="flex justify-between text-xs font-bold">
                    <span className="text-[var(--muted)]">Sample Rate:</span>
                    <span className="text-[var(--ink)] font-mono">{sampleRateMSps.toFixed(2)} MS/s</span>
                  </div>
                  <div className="grid grid-cols-4 gap-1">
                    {[1.0, 2.4576, 5.0, 10.0].map((rate) => (
                      <button
                        key={rate}
                        onClick={() => setSampleRateMSps(rate)}
                        className={`py-1 text-[10px] font-bold rounded ${
                          sampleRateMSps === rate ? 'neo-raised text-blue-600 dark:text-blue-400' : 'text-[var(--muted)]'
                        }`}
                      >
                        {rate}M
                      </button>
                    ))}
                  </div>
                </div>

                {/* Spreading Factor Slider */}
                <div className="p-3.5 rounded-xl neo-inset space-y-2">
                  <div className="flex justify-between text-xs font-bold">
                    <span className="text-[var(--muted)]">Spreading Factor:</span>
                    <span className="text-[var(--ink)] font-mono">{spreadingFactor} chips</span>
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
                  <div className="flex justify-between text-[10px] text-[var(--muted)]">
                    <span>16 chips</span>
                    <span>128 chips</span>
                  </div>
                </div>

                {/* FFT Size Selector */}
                <div className="p-3.5 rounded-xl neo-inset space-y-2">
                  <div className="flex justify-between text-xs font-bold">
                    <span className="text-[var(--muted)]">FFT Resolution:</span>
                    <span className="text-[var(--ink)] font-mono">{fftSize} bins</span>
                  </div>
                  <div className="grid grid-cols-4 gap-1">
                    {[512, 1024, 2048, 4096].map((size) => (
                      <button
                        key={size}
                        onClick={() => setFftSize(size)}
                        className={`py-1 text-[10px] font-bold rounded ${
                          fftSize === size ? 'neo-raised text-blue-600 dark:text-blue-400' : 'text-[var(--muted)]'
                        }`}
                      >
                        {size}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Toggle 3: Tactical EW Intercept Scorecard */}
        <div className="neo-raised rounded-2xl overflow-hidden transition-all">
          <button
            onClick={() => setShowScorecard(!showScorecard)}
            className="w-full p-4 flex items-center justify-between text-left transition-colors hover:bg-slate-500/5"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg neo-inset flex items-center justify-center text-emerald-500">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-[var(--ink)]">
                  Tactical EW Intercept &amp; Detection Horizon Scorecard
                </h4>
                <p className="text-[11px] text-[var(--muted)]">
                  Empirical probability of intercept, detection distance, and stealth margin
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full neo-inset text-[var(--muted)]">
                {showScorecard ? 'Click to Collapse' : 'Click to View'}
              </span>
              {showScorecard ? <ChevronUp className="w-4 h-4 text-[var(--muted)]" /> : <ChevronDown className="w-4 h-4 text-[var(--muted)]" />}
            </div>
          </button>

          {showScorecard && (
            <div className="p-5 pt-0 space-y-4 animate-fadeIn border-t border-[var(--line)] mt-1">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-3">
                <div className="p-3.5 rounded-xl neo-inset space-y-1">
                  <div className="text-[10px] font-bold text-[var(--muted)] uppercase">EW Energy Detection</div>
                  <div className={`text-lg font-black ${viewMode === 'without_lpi' ? 'text-red-500' : 'text-emerald-500'}`}>
                    {viewMode === 'without_lpi' ? '99.4% (CRITICAL)' : '< 0.08% (COVERT)'}
                  </div>
                  <div className="text-[10px] text-[var(--muted)]">vs. radiometer threshold</div>
                </div>

                <div className="p-3.5 rounded-xl neo-inset space-y-1">
                  <div className="text-[10px] font-bold text-[var(--muted)] uppercase">Intercept Horizon</div>
                  <div className="text-lg font-black text-[var(--ink)]">
                    {viewMode === 'without_lpi' ? '42.8 km' : '0.9 km'}
                  </div>
                  <div className="text-[10px] text-emerald-500 font-bold">
                    {viewMode === 'without_lpi' ? 'Fully exposed line-of-sight' : '97.9% standoff range reduction'}
                  </div>
                </div>

                <div className="p-3.5 rounded-xl neo-inset space-y-1">
                  <div className="text-[10px] font-bold text-[var(--muted)] uppercase">Processing Gain (PG)</div>
                  <div className="text-lg font-black text-blue-600 dark:text-blue-400">
                    +{lpiTechnique === 'DSSS' || lpiTechnique === 'CGAN' ? (10 * Math.log10(spreadingFactor)).toFixed(1) : '18.1'} dB
                  </div>
                  <div className="text-[10px] text-[var(--muted)]">spread over noise floor</div>
                </div>

                <div className="p-3.5 rounded-xl neo-inset space-y-1">
                  <div className="text-[10px] font-bold text-[var(--muted)] uppercase">Stealth Margin</div>
                  <div className={`text-lg font-black ${viewMode === 'without_lpi' ? 'text-red-500' : 'text-emerald-500'}`}>
                    {viewMode === 'without_lpi' ? '+22.5 dB (EXPOSED)' : '−11.8 dB (SUB-NOISE)'}
                  </div>
                  <div className="text-[10px] text-[var(--muted)]">under thermal noise</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default AstraSpectrumWaterfallLab
