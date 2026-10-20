import React, { useState, useEffect } from 'react'
import {
  Radio,
  Shield,
  Cpu,
  Layers,
  Send,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Lock,
  Binary,
  Activity,
  Sliders,
  FileCode,
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
import { TransmitterPreparation, SDRHardwareStatus } from '../../types'
import { api } from '../../services/api'

export const TransmitterWorkbenchView: React.FC = () => {
  const [inputText, setInputText] = useState<string>('ASTRA_TACTICAL_BURST_01')
  const [msgType, setMsgType] = useState<string>('TEXT')
  const [prepData, setPrepData] = useState<TransmitterPreparation | null>(null)
  const [isPreparing, setIsPreparing] = useState<boolean>(false)

  // Hardware status probe
  const [sdrStatus, setSdrStatus] = useState<SDRHardwareStatus | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  // Waveform generation preview
  const [waveformResult, setWaveformResult] = useState<any | null>(null)
  const [isGenerating, setIsGenerating] = useState<boolean>(false)

  // Hardware execution
  const [txMode, setTxMode] = useState<'SIMULATION' | 'SDR_HARDWARE'>('SIMULATION')
  const [confirmedRf, setConfirmedRf] = useState<boolean>(false)
  const [isTransmitting, setIsTransmitting] = useState<boolean>(false)
  const [txLog, setTxLog] = useState<any | null>(null)

  // Probe SDR hardware status on load
  useEffect(() => {
    api
      .getSDRHardwareStatus()
      .then((data) => setSdrStatus(data))
      .catch((err) => console.warn('SDR probe error:', err))
  }, [])

  const payloadByteCount = new TextEncoder().encode(inputText).length
  const isPayloadTooLong = payloadByteCount > 256

  // Re-run preparation when input changes
  useEffect(() => {
    let active = true
    setIsPreparing(true)
    setFormError(null)
    const timeout = setTimeout(async () => {
      try {
        const data = await api.prepareTransmitterPayload(inputText, msgType)
        if (active) setPrepData(data)
      } catch (err) {
        console.warn('Preparation error:', err)
      } finally {
        if (active) setIsPreparing(false)
      }
    }, 250)

    return () => {
      active = false
      clearTimeout(timeout)
    }
  }, [inputText, msgType])

  const handleGenerateWaveform = async () => {
    if (!inputText.trim()) {
      setFormError('Payload text cannot be empty for waveform generation.')
      return
    }
    if (isPayloadTooLong) {
      setFormError(`Payload exceeds maximum frame capacity (${payloadByteCount}/256 bytes).`)
      return
    }
    setFormError(null)
    setIsGenerating(true)
    try {
      const res = await api.generateWaveformBurst(inputText)
      setWaveformResult(res)
    } catch (err: any) {
      setFormError(err.message || 'Waveform generation failed.')
    } finally {
      setIsGenerating(false)
    }
  }

  const handleExecuteTransmission = async () => {
    setFormError(null)

    if (!inputText.trim()) {
      setFormError('Validation Error: Payload text cannot be empty.')
      return
    }

    if (isPayloadTooLong) {
      setFormError(`Validation Error: Payload size (${payloadByteCount} bytes) exceeds maximum single-burst capacity (256 bytes).`)
      return
    }

    if (!confirmedRf) {
      setFormError('Safety Lockout: Operator confirmation required. Please check the authorization checkbox prior to burst transmission.')
      return
    }

    if (txMode === 'SDR_HARDWARE' && !sdrStatus?.device_connected) {
      setFormError('Hardware Disconnected: No Ettus USRP B205mini detected via UHD. Switch to SIMULATION mode or connect hardware.')
      return
    }

    setIsTransmitting(true)
    try {
      const res = await api.transmitBurst(inputText, txMode, true)
      setTxLog(res)
    } catch (err: any) {
      setTxLog({ success: false, error: err.message })
    } finally {
      setIsTransmitting(false)
    }
  }

  const presetMessages = [
    { label: 'Tactical Status', text: 'STATUS: Alpha patrol in position. Channel secure.' },
    { label: 'Waypoint Coord', text: 'NAV: WP-4 37.7749N 122.4194W Alt 120m' },
    { label: 'Resource Alert', text: 'LOGISTICS: Battery reserve 42%, link margin 9dB' },
    { label: 'Command ACK', text: 'COMMAND_ACK: Mission payload received and verified.' },
  ]

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-zinc-900/80 border border-zinc-800 p-4 rounded-xl flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2">
            <Radio className="w-5 h-5 text-emerald-400" />
            <h2 className="text-base font-bold font-mono text-zinc-100">
              Transmitter Workbench &amp; Signal Synthesis
            </h2>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5 font-sans">
            Cryptographic framing, Reed-Solomon coding, and neural waveform generation for Ettus USRP B205mini
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono">
          <span className="text-zinc-500">Mode:</span>
          <select
            value={txMode}
            onChange={(e) => {
              setTxMode(e.target.value as any)
              setFormError(null)
            }}
            className="bg-zinc-950 border border-zinc-800 rounded px-2 py-1 text-zinc-200"
          >
            <option value="SIMULATION">SIMULATION (Software Loopback)</option>
            <option value="SDR_HARDWARE">
              SDR_HARDWARE {sdrStatus && !sdrStatus.device_connected ? '(USRP Offline)' : '(USRP B205mini)'}
            </option>
          </select>
        </div>
      </div>

      {/* Hardware Disconnected Notice when SDR_HARDWARE selected */}
      {txMode === 'SDR_HARDWARE' && sdrStatus && !sdrStatus.device_connected && (
        <div className="p-3 bg-amber-950/40 border border-amber-800/80 rounded-xl text-xs font-mono text-amber-300 flex items-start space-x-2.5">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-bold block">SDR Hardware Disconnected</span>
            <p className="text-zinc-300 text-[11px] leading-relaxed">
              No Ettus USRP B205mini detected via UHD drivers on USB/PCIe. Transmissions in SDR_HARDWARE mode will be safely rejected by the backend. Select <span className="text-emerald-400 font-semibold">SIMULATION</span> to synthesize and record baseband bursts.
            </p>
          </div>
        </div>
      )}

      {/* Section 1: Payload Preparation & Presets */}
      <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 font-mono">
              1. Payload Ingestion &amp; Message Presets
            </h3>
          </div>
          <span
            className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
              isPayloadTooLong
                ? 'bg-rose-950/60 border-rose-800 text-rose-300 font-bold'
                : 'bg-zinc-950 border-zinc-800 text-zinc-400'
            }`}
          >
            {payloadByteCount} / 256 bytes &bull; UTF-8 Encoded
          </span>
        </div>

        {/* Preset Buttons */}
        <div className="flex flex-wrap gap-2 text-xs font-mono">
          {presetMessages.map((p, idx) => (
            <button
              key={idx}
              onClick={() => {
                setInputText(p.text)
                setFormError(null)
              }}
              className="px-2.5 py-1 rounded bg-zinc-950 hover:bg-zinc-800 text-zinc-300 border border-zinc-850 hover:border-zinc-700 transition-colors"
            >
              {p.label}
            </button>
          ))}
        </div>

        <div className="flex items-center space-x-3">
          <textarea
            rows={2}
            value={inputText}
            onChange={(e) => {
              setInputText(e.target.value)
              setFormError(null)
            }}
            placeholder="Type message to encode, encrypt, and synthesize..."
            className={`flex-1 bg-zinc-950 border rounded-lg p-2.5 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none font-mono resize-none ${
              isPayloadTooLong ? 'border-rose-600 focus:border-rose-500' : 'border-zinc-800 focus:border-emerald-500'
            }`}
          />
          <button
            onClick={handleGenerateWaveform}
            disabled={isGenerating || !inputText.trim() || isPayloadTooLong}
            className="px-4 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white font-mono text-xs font-semibold rounded-lg flex flex-col items-center justify-center transition-colors shadow-md h-full shrink-0"
          >
            <Cpu className="w-4 h-4 mb-1" />
            <span>{isGenerating ? 'Generating...' : 'Synthesize'}</span>
          </button>
        </div>
      </div>

      {/* Section 2: Cryptographic Container & Error Correction Parameters */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Crypto Container */}
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-purple-300 font-mono flex items-center space-x-2">
              <Shield className="w-4 h-4 text-purple-400" />
              <span>2. Cryptographic Security Container</span>
            </h3>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-purple-950/80 text-purple-300 border border-purple-800">
              AES-256-GCM v2
            </span>
          </div>

          <div className="space-y-1.5 text-xs font-mono text-zinc-300">
            <div className="flex justify-between">
              <span className="text-zinc-500">Authenticated Cipher:</span>
              <span className="text-zinc-200">AES-256 (Galois/Counter Mode)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">IV Nonce (12 Bytes):</span>
              <span className="text-purple-400 truncate max-w-[200px]">
                {prepData?.crypto_envelope?.nonce_hex || 'a7 3e 99 c1 04 f2 88 d9 41 0b e3 12'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">GMAC Tag (16 Bytes):</span>
              <span className="text-purple-400 truncate max-w-[200px]">
                {prepData?.crypto_envelope?.tag_hex || '8e fa 44 19 c0 2e d8 3f 71 9a 05 61'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Envelope Total:</span>
              <span className="text-zinc-200 font-bold">
                {prepData?.crypto_envelope?.envelope_bytes || 0} Bytes (+28B Overhead)
              </span>
            </div>
          </div>
        </div>

        {/* Error Correction & Framing */}
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-cyan-300 font-mono flex items-center space-x-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              <span>3. Forward Error Correction (FEC)</span>
            </h3>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-950/80 text-cyan-300 border border-cyan-800">
              RS(42, 34)
            </span>
          </div>

          <div className="space-y-1.5 text-xs font-mono text-zinc-300">
            <div className="flex justify-between">
              <span className="text-zinc-500">Block Code:</span>
              <span className="text-zinc-200">Reed-Solomon RS(42, 34)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Blocks Count:</span>
              <span className="text-cyan-400 font-bold">
                {prepData?.error_correction?.total_blocks || 1} Block(s)
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Parity Symbols:</span>
              <span className="text-zinc-200">8 Symbols / Block (+{prepData?.error_correction?.parity_overhead_bytes || 8}B total)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Error Correction Margin:</span>
              <span className="text-emerald-400 font-bold">t = 4 symbol errors corrected</span>
            </div>
          </div>
        </div>
      </div>

      {/* Section 3: Wire Memory Map & Frame Inspector */}
      <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-2">
        <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 font-mono flex items-center space-x-2">
          <Binary className="w-4 h-4 text-emerald-400" />
          <span>Physical Frame Wire Memory Map</span>
        </h3>
        <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-850 font-mono text-xs text-zinc-300 space-y-1 overflow-x-auto leading-relaxed">
          {(prepData?.wire_hex_memory_map || []).map((line, idx) => (
            <div key={idx} className="whitespace-nowrap">
              {line}
            </div>
          ))}
        </div>
      </div>

      {/* Section 4: Waveform Generation Preview Chart */}
      {waveformResult && (
        <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 font-mono flex items-center space-x-2">
                <Activity className="w-4 h-4 text-emerald-400" />
                <span>4. Synthesized Baseband I/Q Waveform Preview</span>
              </h3>
              <p className="text-[11px] text-zinc-400 font-sans">
                Neural generator spread spectrum samples (first 64 discrete baseband time steps)
              </p>
            </div>
            <div className="flex items-center space-x-3 text-xs font-mono">
              <span className="text-zinc-400">Peak: <strong className="text-zinc-200">{waveformResult.peak_amplitude}</strong></span>
              <span className="text-zinc-400">RMS: <strong className="text-emerald-400">{waveformResult.rms_amplitude}</strong></span>
              <span className="text-zinc-400">PAPR: <strong className="text-cyan-400">{waveformResult.papr_db} dB</strong></span>
            </div>
          </div>

          <div className="h-60 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={waveformResult.time_series_preview}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="sample" stroke="#71717a" fontSize={11} />
                <YAxis stroke="#71717a" fontSize={11} domain={[-1.5, 1.5]} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', fontSize: '11px', fontFamily: 'monospace' }}
                />
                <Line type="monotone" dataKey="i" stroke="#10b981" dot={false} strokeWidth={2} name="In-Phase (I)" />
                <Line type="monotone" dataKey="q" stroke="#38bdf8" dot={false} strokeWidth={2} name="Quadrature (Q)" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Section 5: SDR Execution & Safety Confirmation */}
      <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 font-mono flex items-center space-x-2">
            <Radio className="w-4 h-4 text-emerald-400" />
            <span>5. Transmission Execution &amp; Hardware Lockout</span>
          </h3>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
            2.484 GHz &bull; 0 dB TX Gain
          </span>
        </div>

        {/* Form Validation / Safety Error Banner */}
        {formError && (
          <div className="p-3 bg-rose-950/40 border border-rose-800/80 rounded-lg text-xs font-mono text-rose-300 flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span className="font-semibold">{formError}</span>
          </div>
        )}

        <div className="p-3 bg-zinc-950 border border-zinc-850 rounded-lg flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs font-mono">
          <label className="flex items-center space-x-2.5 cursor-pointer">
            <input
              type="checkbox"
              checked={confirmedRf}
              onChange={(e) => {
                setConfirmedRf(e.target.checked)
                if (e.target.checked) setFormError(null)
              }}
              className="w-4 h-4 rounded border-zinc-700 bg-zinc-900 text-emerald-500 focus:ring-0 cursor-pointer"
            />
            <span className="text-zinc-200 font-semibold">
              Confirm authorized burst transmission on ISM Channel 14
            </span>
          </label>

          <button
            onClick={handleExecuteTransmission}
            disabled={!confirmedRf || isTransmitting}
            className={`px-5 py-2 rounded-lg font-mono text-xs font-bold flex items-center space-x-2 transition-colors ${
              !confirmedRf || isTransmitting
                ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed'
                : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg'
            }`}
          >
            <Send className="w-4 h-4" />
            <span>{isTransmitting ? 'Transmitting...' : 'Transmit Burst'}</span>
          </button>
        </div>

        {/* Transmission Outcome Log */}
        {txLog && (
          <div
            className={`p-3 rounded-lg border font-mono text-xs space-y-1 ${
              txLog.success
                ? 'bg-emerald-950/30 border-emerald-800/60 text-emerald-300'
                : 'bg-rose-950/30 border-rose-800/60 text-rose-300'
            }`}
          >
            <div className="font-bold flex items-center space-x-1.5">
              {txLog.success ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
              <span>{txLog.status || txLog.error}</span>
            </div>
            {txLog.details && <p className="text-zinc-400">{txLog.details}</p>}
            {txLog.airtime_ms && (
              <p className="text-[11px] text-zinc-400">
                Airtime: {txLog.airtime_ms} ms &bull; Samples: {txLog.samples_transmitted} &bull; Mode: {txLog.mode}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
