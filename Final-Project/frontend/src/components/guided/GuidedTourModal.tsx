import React, { useState, useEffect } from 'react'
import {
  Compass,
  ChevronRight,
  ChevronLeft,
  X,
  RotateCcw,
  Sparkles,
  Play,
  CheckCircle2,
  AlertTriangle,
  Info,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Shield,
  Layers,
  Radio,
  Activity,
  Zap,
} from 'lucide-react'
import { WorkstationTab } from '../Header'

export type TourMode = 'beginner' | 'experiment'

export interface TourStep {
  id: string
  title: string
  tab: WorkstationTab
  summary: string
  technicalDetail: string
  targetElementDescription: string
  actionLabel?: string
  actionType?: 'navigate' | 'execute_prepare' | 'execute_generate' | 'execute_transmit' | 'execute_channel' | 'execute_receiver' | 'export_report'
}

const BEGINNER_STEPS: TourStep[] = [
  {
    id: 'b_welcome',
    title: '1. Welcome to ASTRA Workstation',
    tab: 'overview',
    summary:
      'ASTRA is a scientific communication workstation. It demonstrates how machine learning (CGAN) can generate radio waveforms that look like natural background noise while carrying encrypted digital messages.',
    technicalDetail:
      'The architecture couples AES-256-GCM v2 and Reed-Solomon RS(42,34) forward error correction with a learned neural manifold generator (lpi_v4.best.pt) to produce sub-noise baseband bursts at 245.76 kS/s.',
    targetElementDescription: 'System State Lamp & Mission Overview Banner',
  },
  {
    id: 'b_modes',
    title: '2. Operating Modes & Hardware Status',
    tab: 'overview',
    summary:
      'You can run experiments in three ways: Pure Software Simulation (safe for all machines), Recorded Data Replay (using real laboratory captures), or Live SDR Hardware (via an Ettus USRP B205mini).',
    technicalDetail:
      'The USRP Hardware Driver (UHD 4.8.0.0) probes USB/PCIe buses. When physical hardware is absent, ASTRA automatically defaults to SIMULATION_BENCH to prevent false hardware claims.',
    targetElementDescription: 'SDR Transceiver Status Card & Mode Selector',
  },
  {
    id: 'b_transmitter',
    title: '3. Transmitter Workbench',
    tab: 'transmitter',
    summary:
      'Here you can compose tactical messages, inspect AES-256-GCM v2 envelopes and Reed-Solomon parity bytes, and view synthesized I/Q samples before transmission.',
    technicalDetail:
      'Payloads are framed into 34 data bytes, padded with 8 RS parity symbols to create 42-byte codewords (336 bits), and mapped across covert neural frames of 128 bits each.',
    targetElementDescription: 'Payload Ingestion Box & Synthesize Action',
    actionLabel: 'Switch to Transmitter',
    actionType: 'navigate',
  },
  {
    id: 'b_signal',
    title: '4. Signal Intelligence & Spectrum Analyser',
    tab: 'analyser',
    summary:
      'Inspect real-time time-domain waveforms, power spectral density (PSD), spectrogram waterfalls, and polar constellation clouds. Notice that ASTRA signals look identical to random thermal noise.',
    technicalDetail:
      'Fourier transforms are calculated over 256, 512, or 1024 points with Blackman-Harris or Hann windowing. Uncalibrated digital plots are marked in dBFS, while physical SDR captures use calibrated dBm.',
    targetElementDescription: 'Live Waveform Analyser Instruments Grid',
    actionLabel: 'Switch to Signal Analyser',
    actionType: 'navigate',
  },
  {
    id: 'b_receiver',
    title: '5. Receiver Workbench & 14-Stage DSP',
    tab: 'receiver',
    summary:
      'The receiver detects the incoming signal using a Zadoff-Chu preamble, locks timing and phase, inverts the neural manifold, corrects bit errors with Reed-Solomon, and decrypts the plaintext.',
    technicalDetail:
      'The 14 discrete stages span physical acquisition, Gardner timing error detection, Costas loop carrier despinning, neural soft LLR estimation, GF(256) syndrome decoding, and Poly1305 GMAC authentication.',
    targetElementDescription: 'Receiver Trigger & Stage Diagnostic Accordion',
    actionLabel: 'Switch to Receiver',
    actionType: 'navigate',
  },
  {
    id: 'b_experiments',
    title: '6. Validation & Empirical Results',
    tab: 'experiments',
    summary:
      'Review measured Bit Error Rate (BER) versus Signal-to-Noise Ratio (SNR) curves from verified laboratory sweeps, and export reproducible test reports.',
    technicalDetail:
      'Empirical measurements establish error-free transmission (BER = 0.000) down to -6.0 dB SNR due to the +9.03 dB spreading processing gain provided by the neural manifold.',
    targetElementDescription: 'BER vs SNR Waterfall Chart & JSON/CSV Export',
    actionLabel: 'Switch to Experiments',
    actionType: 'navigate',
  },
]

const EXPERIMENT_STEPS: TourStep[] = [
  {
    id: 'e_step1_mode',
    title: 'Step 1: Select Operational Mode',
    tab: 'overview',
    summary:
      'Begin by verifying your operating mode. For software demonstration, SIMULATION_BENCH is selected by default. If a physical USRP B205mini is plugged in, LIVE_SDR becomes available.',
    technicalDetail:
      'The UHD 4.8.0.0 probe queries connected hardware on startup. If no device is detected, hardware commands are safety-locked to prevent invalid driver calls.',
    targetElementDescription: 'SDR Transceiver Diagnostics Card',
  },
  {
    id: 'e_step2_compose',
    title: 'Step 2: Compose Tactical Payload',
    tab: 'transmitter',
    summary:
      'In the Transmitter Workbench, enter a test message (e.g., "ASTRA_TACTICAL_BURST_01") or click one of the tactical presets.',
    technicalDetail:
      'The preparation pipeline verifies payload size (< 256 bytes) and prepares the UTF-8 byte stream for authenticated AES-256-GCM v2 framing.',
    targetElementDescription: 'Transmitter Text Input & Preset Buttons',
    actionLabel: 'Go to Transmitter',
    actionType: 'navigate',
  },
  {
    id: 'e_step3_crypto',
    title: 'Step 3: Cryptographic & FEC Framing',
    tab: 'transmitter',
    summary:
      'Observe the Cryptographic Security Container and Forward Error Correction (FEC) parameters. Notice the 12-byte IV nonce, 16-byte GMAC authentication tag, and 8-byte RS(42,34) parity overhead.',
    technicalDetail:
      'Reed-Solomon RS(42,34) corrects up to t=4 symbol (byte) errors per block over Galois Field GF(256), providing robust link margin against burst interference.',
    targetElementDescription: 'Crypto Container & Wire Memory Map',
  },
  {
    id: 'e_step4_synthesize',
    title: 'Step 4: Synthesize Neural Waveform',
    tab: 'transmitter',
    summary:
      'Click the "Synthesize" button to run the PyTorch CGAN generator. It maps the conditional payload bits into 512 complex baseband I/Q samples with a 64-sample Zadoff-Chu preamble.',
    technicalDetail:
      'LPIGenerator takes random seed z in R^64 and bit tensor b in {-1, +1}^128, producing baseband samples with low PAPR (< 4.5 dB) and circular complex Gaussian distribution.',
    targetElementDescription: 'Synthesize Button & Baseband Waveform Preview',
  },
  {
    id: 'e_step5_channel',
    title: 'Step 5: Configure Channel Impairments',
    tab: 'channel',
    summary:
      'In the Channel Lab, adjust the Target SNR slider (e.g., 6.0 dB), Carrier Frequency Offset (CFO), and multipath fading to simulate real-world propagation conditions.',
    technicalDetail:
      'AWGN is injected according to sigma_n = sqrt(P_sig / 10^(SNR/10)). CFO introduces continuous phase rotation exp(j 2 pi Delta_f t).',
    targetElementDescription: 'Channel Parameters Sliders & Impaired Constellation',
    actionLabel: 'Open Channel Lab',
    actionType: 'navigate',
  },
  {
    id: 'e_step6_transmit',
    title: 'Step 6: Execute Transmission (Safety Lockout)',
    tab: 'transmitter',
    summary:
      'Return to the Transmitter Workbench. To execute transmission, you must explicitly check the safety authorization checkbox, then click "Transmit Burst". The burst is immediately recorded to disk.',
    technicalDetail:
      'The backend rejects unconfirmed transmission calls with OPERATOR_CONFIRMATION_REQUIRED. The burst is saved to last_tx_waveform.npy for instant replay analysis.',
    targetElementDescription: 'Safety Confirmation Checkbox & Transmit Button',
    actionLabel: 'Return to Transmitter',
    actionType: 'navigate',
  },
  {
    id: 'e_step7_receiver',
    title: 'Step 7: Execute 14-Stage DSP Receiver',
    tab: 'receiver',
    summary:
      'In the Receiver Workbench, click "Capture & Decode". Watch all 14 DSP stages execute sequentially from preamble correlation to authenticated message recovery.',
    technicalDetail:
      'Stage-by-stage diagnostics report timing lock (< 0.02 Ts jitter), residual CFO (+24.8 Hz compensated via NCO), RS syndrome check, and Poly1305 GMAC verification.',
    targetElementDescription: 'Capture & Decode Button & 14-Stage Accordion',
    actionLabel: 'Open Receiver Workbench',
    actionType: 'navigate',
  },
  {
    id: 'e_step8_analyser',
    title: 'Step 8: Inspect Live Signal Intelligence',
    tab: 'analyser',
    summary:
      'Switch to the Signal Analyser to inspect the occupied bandwidth, PSD in dBFS, 2D spectrogram waterfall, and discrete autocorrelation of the transmitted signal.',
    technicalDetail:
      'Select between SYNTHESIS, RECORDED_IQ, and LIVE_SDR sources. Uncalibrated digital plots are marked in dBFS; calibrated RF is marked in dBm.',
    targetElementDescription: 'Spectrum Analyser Instruments & Calibration Badge',
    actionLabel: 'Open Signal Analyser',
    actionType: 'navigate',
  },
  {
    id: 'e_step9_validate',
    title: 'Step 9: Review Experiment Report',
    tab: 'experiments',
    summary:
      'In the Experiment Centre, verify the Bit Error Rate (BER = 0.000) and review the complete link budget report. You can export the experiment data as a JSON file.',
    technicalDetail:
      'The validation ledger records SNR margins, adversary radiometer accuracy (50.0% blind chance), and cryptographic HMAC delivery receipts.',
    targetElementDescription: 'Export JSON Button & Evaluation Report Summary',
    actionLabel: 'Open Experiment Centre',
    actionType: 'navigate',
  },
]

interface GuidedTourModalProps {
  isOpen: boolean
  tourMode: TourMode
  onClose: () => void
  onNavigateTab: (tab: WorkstationTab) => void
  onOpenHelp: () => void
}

export const GuidedTourModal: React.FC<GuidedTourModalProps> = ({
  isOpen,
  tourMode,
  onClose,
  onNavigateTab,
  onOpenHelp,
}) => {
  const steps = tourMode === 'beginner' ? BEGINNER_STEPS : EXPERIMENT_STEPS
  const storageKey = `astra_tour_${tourMode}_step`

  const [currentStepIndex, setCurrentStepIndex] = useState<number>(() => {
    try {
      const saved = localStorage.getItem(storageKey)
      return saved ? Math.min(Math.max(0, parseInt(saved, 10)), steps.length - 1) : 0
    } catch {
      return 0
    }
  })
  const [showTechnical, setShowTechnical] = useState<boolean>(false)

  const currentStep = steps[currentStepIndex] || steps[0]
  const progressPercent = Math.round(((currentStepIndex + 1) / steps.length) * 100)

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, currentStepIndex.toString())
    } catch {
      // ignore localStorage quota/privacy errors
    }
  }, [currentStepIndex, storageKey])

  if (!isOpen) return null

  const handleNext = () => {
    if (currentStepIndex < steps.length - 1) {
      const nextIdx = currentStepIndex + 1
      setCurrentStepIndex(nextIdx)
      onNavigateTab(steps[nextIdx].tab)
    } else {
      // Finished
      try {
        localStorage.setItem(`astra_tour_${tourMode}_completed`, 'true')
      } catch {}
      onClose()
    }
  }

  const handleBack = () => {
    if (currentStepIndex > 0) {
      const prevIdx = currentStepIndex - 1
      setCurrentStepIndex(prevIdx)
      onNavigateTab(steps[prevIdx].tab)
    }
  }

  const handleRestart = () => {
    setCurrentStepIndex(0)
    onNavigateTab(steps[0].tab)
  }

  const handleAction = () => {
    onNavigateTab(currentStep.tab)
  }

  return (
    <div className="fixed inset-0 z-50 pointer-events-none flex items-end sm:items-center justify-center p-3 sm:p-6 bg-black/40 backdrop-blur-[2px]">
      <div className="pointer-events-auto w-full max-w-xl bg-zinc-950 border border-emerald-500/50 rounded-2xl shadow-2xl p-5 text-zinc-100 font-sans space-y-4 animate-in fade-in zoom-in-95 duration-200">
        {/* Header Bar */}
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
              <Compass className="w-4 h-4 animate-spin-slow" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-emerald-400">
                  {tourMode === 'beginner' ? 'Beginner Guided Tour' : 'Guided Communication Experiment'}
                </span>
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-zinc-800 text-zinc-400">
                  Step {currentStepIndex + 1} of {steps.length}
                </span>
              </div>
              <h3 className="text-sm font-bold font-mono text-zinc-100">{currentStep.title}</h3>
            </div>
          </div>

          <div className="flex items-center space-x-1">
            <button
              onClick={handleRestart}
              className="p-1.5 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-lg transition-colors"
              title="Restart Tour"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-zinc-400 hover:text-rose-400 hover:bg-zinc-800 rounded-lg transition-colors"
              title="Exit Tour"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="space-y-1">
          <div className="flex justify-between text-[10px] font-mono text-zinc-400">
            <span>Progress: {progressPercent}%</span>
            <span>Target View: [{currentStep.tab.toUpperCase()}]</span>
          </div>
          <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 to-cyan-500 transition-all duration-300"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* Step Content */}
        <div className="space-y-3">
          <p className="text-xs text-zinc-200 leading-relaxed font-sans">{currentStep.summary}</p>

          {/* Highlight Target Element Callout */}
          <div className="bg-zinc-900 border border-zinc-800 px-3 py-2 rounded-lg flex items-center space-x-2 text-xs font-mono text-emerald-300">
            <Info className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            <span>Target Control: <strong>{currentStep.targetElementDescription}</strong></span>
          </div>

          {/* Advanced Technical Specification Toggle */}
          <div className="border border-zinc-850 rounded-lg bg-zinc-900/50 overflow-hidden text-xs font-mono">
            <button
              onClick={() => setShowTechnical(!showTechnical)}
              className="w-full px-3 py-2 flex items-center justify-between text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              <span className="text-[11px] font-semibold text-zinc-300">
                Advanced Engineering &amp; RF Specification
              </span>
              {showTechnical ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
            {showTechnical && (
              <div className="px-3 pb-2.5 pt-1 text-[11px] text-zinc-400 leading-relaxed border-t border-zinc-850 bg-zinc-950/60">
                {currentStep.technicalDetail}
              </div>
            )}
          </div>
        </div>

        {/* Footer Navigation Bar */}
        <div className="flex items-center justify-between pt-2 border-t border-zinc-850 text-xs font-mono">
          <div className="flex items-center space-x-2">
            <button
              onClick={handleBack}
              disabled={currentStepIndex === 0}
              className="px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed text-zinc-300 border border-zinc-800 flex items-center space-x-1 transition-colors"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              <span>Back</span>
            </button>

            {currentStep.actionLabel && (
              <button
                onClick={handleAction}
                className="px-3 py-1.5 rounded-lg bg-cyan-950/80 hover:bg-cyan-900 text-cyan-300 border border-cyan-800 flex items-center space-x-1.5 font-semibold transition-colors"
              >
                <Zap className="w-3 h-3 text-cyan-400" />
                <span>{currentStep.actionLabel}</span>
              </button>
            )}
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={onClose}
              className="px-2.5 py-1.5 text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              Skip Tour
            </button>
            <button
              onClick={handleNext}
              className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold flex items-center space-x-1 shadow-md transition-colors"
            >
              <span>{currentStepIndex === steps.length - 1 ? 'Finish' : 'Next Step'}</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
