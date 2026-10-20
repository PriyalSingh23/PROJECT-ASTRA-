import React, { useState, useEffect } from 'react'
import {
  Activity,
  Radio,
  CheckCircle2,
  AlertTriangle,
  Play,
  RotateCcw,
  Shield,
  Layers,
  ChevronDown,
  ChevronRight,
  Zap,
  Terminal,
  Binary,
  Info,
} from 'lucide-react'
import { ReceiverDSPPipelineResult, ReceiverDSPStage, SDRHardwareStatus } from '../../types'
import { api } from '../../services/api'

export const ReceiverWorkbenchView: React.FC = () => {
  const [rxMode, setRxMode] = useState<'SIMULATION' | 'LIVE_SDR' | 'RECORDED_IQ'>('SIMULATION')
  const [targetSnr, setTargetSnr] = useState<number>(6.0)
  const [isProcessing, setIsProcessing] = useState<boolean>(false)
  const [pipelineResult, setPipelineResult] = useState<ReceiverDSPPipelineResult | null>(null)
  const [expandedStage, setExpandedStage] = useState<number | null>(null)
  const [sdrStatus, setSdrStatus] = useState<SDRHardwareStatus | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  useEffect(() => {
    api
      .getSDRHardwareStatus()
      .then((data) => setSdrStatus(data))
      .catch((err) => console.warn('SDR status check error:', err))
  }, [])

  const handleCaptureAndProcess = async () => {
    setIsProcessing(true)
    setErrorMsg(null)
    try {
      const res = await api.captureAndProcessReceiver(rxMode, targetSnr)
      setPipelineResult(res)
    } catch (err: any) {
      setErrorMsg(err.message || 'Receiver capture failed.')
    } finally {
      setIsProcessing(false)
    }
  }

  const isSuccess = pipelineResult?.overall_status === 'SUCCESS'

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-zinc-900/80 border border-zinc-800 p-4 rounded-xl flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2">
            <Activity className="w-5 h-5 text-cyan-400" />
            <h2 className="text-base font-bold font-mono text-zinc-100">
              Receiver Workbench &amp; 14-Stage DSP Pipeline
            </h2>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5 font-sans">
            Zadoff-Chu preamble synchronization, neural manifold inversion, and authenticated AES-GCM recovery
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono">
          <span className="text-zinc-500">Source:</span>
          <select
            value={rxMode}
            onChange={(e) => {
              setRxMode(e.target.value as any)
              setErrorMsg(null)
            }}
            className="bg-zinc-950 border border-zinc-800 rounded px-2 py-1 text-zinc-200"
          >
            <option value="SIMULATION">SIMULATION (Software Test Bench)</option>
            <option value="RECORDED_IQ">RECORDED_IQ (last_tx_waveform.npy)</option>
            <option value="LIVE_SDR">
              LIVE_SDR {sdrStatus && !sdrStatus.device_connected ? '(USRP Offline)' : '(USRP B205mini)'}
            </option>
          </select>
        </div>
      </div>

      {/* Disconnected Hardware Alert for LIVE_SDR */}
      {rxMode === 'LIVE_SDR' && sdrStatus && !sdrStatus.device_connected && (
        <div className="p-3 bg-amber-950/40 border border-amber-800/80 rounded-xl text-xs font-mono text-amber-300 flex items-start space-x-2.5">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-bold block">SDR Hardware Disconnected</span>
            <p className="text-zinc-300 text-[11px] leading-relaxed">
              No physical Ettus USRP B205mini detected via UHD drivers. Attempting LIVE_SDR capture will fail with <span className="text-rose-400">HARDWARE_NOT_FOUND</span>. Switch to <span className="text-cyan-400 font-semibold">SIMULATION</span> or <span className="text-purple-400 font-semibold">RECORDED_IQ</span> to decode signals.
            </p>
          </div>
        </div>
      )}

      {/* Recorded IQ file information */}
      {rxMode === 'RECORDED_IQ' && (
        <div className="p-3 bg-purple-950/30 border border-purple-800/60 rounded-xl text-xs font-mono text-purple-300 flex items-start space-x-2.5">
          <Info className="w-4 h-4 text-purple-400 shrink-0 mt-0.5" />
          <p className="text-zinc-300 text-[11px] leading-relaxed">
            Reading baseband burst from <span className="text-purple-300 font-semibold">last_tx_waveform.npy</span> on disk. If not yet transmitted, synthesize a burst from the Transmitter Workbench first.
          </p>
        </div>
      )}

      {/* Error Message Alert */}
      {errorMsg && (
        <div className="p-3 bg-rose-950/40 border border-rose-800/80 rounded-xl text-xs font-mono text-rose-300 flex items-center space-x-2">
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
          <span className="font-semibold">{errorMsg}</span>
        </div>
      )}

      {/* Control Card: Capture Trigger & SNR Control */}
      <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs font-mono">
          <div className="space-y-1">
            <span className="text-zinc-400 block">RF Tuning:</span>
            <span className="text-zinc-200 font-bold block">2.484000 GHz</span>
            <span className="text-[10px] text-zinc-500">ISM Ch 14 &bull; 245.76 kS/s</span>
          </div>

          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-zinc-400">Simulation SNR:</span>
              <span className="text-cyan-400 font-bold">{targetSnr.toFixed(1)} dB</span>
            </div>
            <input
              type="range"
              min={-4}
              max={14}
              step={0.5}
              value={targetSnr}
              onChange={(e) => setTargetSnr(Number(e.target.value))}
              className="w-full accent-cyan-500 cursor-pointer"
            />
            <div className="flex justify-between text-[9px] text-zinc-500">
              <span>-4 dB (Deep Sub-noise)</span>
              <span>+14 dB (Clean)</span>
            </div>
          </div>

          <div className="flex items-center justify-end">
            <button
              onClick={handleCaptureAndProcess}
              disabled={isProcessing}
              className="px-5 py-2.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-zinc-800 text-white font-mono text-xs font-bold rounded-lg flex items-center space-x-2 transition-colors shadow-lg"
            >
              <Play className="w-4 h-4" />
              <span>{isProcessing ? 'Processing DSP...' : 'Capture & Decode'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Pipeline Status Summary Card */}
      {pipelineResult && (
        <div
          className={`border p-4 rounded-xl space-y-3 ${
            isSuccess
              ? 'bg-zinc-900/60 border-zinc-800'
              : 'bg-rose-950/20 border-rose-800/60'
          }`}
        >
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-zinc-800 pb-3">
            <div className="flex items-center space-x-2">
              {isSuccess ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
              )}
              <div>
                <h3
                  className={`text-xs font-bold uppercase tracking-wider font-mono ${
                    isSuccess ? 'text-emerald-300' : 'text-rose-300'
                  }`}
                >
                  {pipelineResult.recovery_status}
                </h3>
                <p className="text-[11px] text-zinc-400 font-sans">
                  {isSuccess ? (
                    <>
                      Recovered Plaintext: <strong className="text-zinc-100 font-mono">"{pipelineResult.recovered_plaintext}"</strong>
                    </>
                  ) : (
                    <span className="text-rose-400 font-mono">
                      {pipelineResult.details || pipelineResult.error || 'Frame decoding or authentication failed.'}
                    </span>
                  )}
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-3 text-xs font-mono">
              <span className="text-zinc-400">
                Stages:{' '}
                <strong className={isSuccess ? 'text-zinc-200' : 'text-rose-400'}>
                  {pipelineResult.stages?.filter((s) => s.state === 'COMPLETED').length || 0} / {pipelineResult.total_stages || 14}
                </strong>
              </span>
              <span className="text-zinc-400">
                BER: <strong className={isSuccess ? 'text-emerald-400' : 'text-rose-400'}>{pipelineResult.bit_error_rate_ber.toFixed(3)}</strong>
              </span>
              <span className="text-zinc-400">
                Total Latency: <strong className="text-cyan-400">{pipelineResult.total_duration_ms} ms</strong>
              </span>
            </div>
          </div>

          {/* Cryptographic ACK receipt */}
          <div className="flex items-center justify-between text-xs font-mono bg-zinc-950 p-2.5 rounded-lg border border-zinc-850">
            <span className="text-zinc-500">Receiver Signed HMAC Receipt:</span>
            <span className={`truncate max-w-sm font-bold ${isSuccess ? 'text-emerald-400' : 'text-zinc-500'}`}>
              {pipelineResult.signed_ack_receipt}
            </span>
          </div>
        </div>
      )}

      {/* Section: 14-Stage DSP Pipeline Trace */}
      <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 font-mono flex items-center space-x-2">
            <Activity className="w-4 h-4 text-cyan-400" />
            <span>Receiver DSP Pipeline Execution Trace</span>
          </h3>
          <span className="text-[10px] font-mono text-zinc-500">
            14 Discrete Physical-Layer Stages
          </span>
        </div>

        {pipelineResult ? (
          <div className="divide-y divide-zinc-800/60 border border-zinc-800 rounded-lg overflow-hidden bg-zinc-950">
            {pipelineResult.stages.map((stage: ReceiverDSPStage) => {
              const isExpanded = expandedStage === stage.stage_id

              return (
                <div key={stage.stage_id} className="p-3 hover:bg-zinc-900/40 transition-colors">
                  <div
                    onClick={() => setExpandedStage(isExpanded ? null : stage.stage_id)}
                    className="flex items-center justify-between cursor-pointer"
                  >
                    <div className="flex items-center space-x-3">
                      <span className="text-[10px] font-mono text-zinc-500 w-6">
                        #{stage.stage_id}
                      </span>
                      <span className="w-2 h-2 rounded-full bg-emerald-400" />
                      <span className="text-xs font-bold font-mono text-zinc-200">
                        {stage.name}
                      </span>
                    </div>

                    <div className="flex items-center space-x-3 text-xs font-mono">
                      <span className="text-emerald-400 font-semibold">{stage.result}</span>
                      <span className="text-zinc-500">{stage.duration_ms} ms</span>
                      {isExpanded ? (
                        <ChevronDown className="w-4 h-4 text-zinc-400" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-zinc-400" />
                      )}
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="mt-2.5 pt-2.5 border-t border-zinc-800/80 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono text-zinc-400 bg-zinc-900/50 p-2.5 rounded">
                      <div>
                        <span className="text-zinc-500 block text-[10px]">INPUT:</span>
                        <span className="text-zinc-300">{stage.input_spec}</span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[10px]">OUTPUT:</span>
                        <span className="text-cyan-300">{stage.output_spec}</span>
                      </div>
                      <div className="sm:col-span-2 mt-1">
                        <span className="text-zinc-500 block text-[10px]">NOTES:</span>
                        <span className="text-zinc-400">{stage.notes}</span>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ) : (
          <div className="text-center py-10 bg-zinc-950 rounded-lg border border-zinc-850 text-zinc-500 text-xs font-mono">
            Click "Capture &amp; Decode" above to run the 14-stage DSP receiver pipeline.
          </div>
        )}
      </div>
    </div>
  )
}
