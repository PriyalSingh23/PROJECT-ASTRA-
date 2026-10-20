import React, { useState } from 'react'
import {
  ArrowRight,
  Shield,
  Layers,
  Cpu,
  Radio,
  Zap,
  Activity,
  CheckCircle2,
  Lock,
  FileCode,
  Info,
  ExternalLink,
} from 'lucide-react'

interface PipelineStageInfo {
  id: string
  title: string
  category: 'TX' | 'RF' | 'RX'
  module: string
  status: 'VERIFIED' | 'SIMULATION' | 'HARDWARE_READY'
  purpose: string
  inputSpec: string
  outputSpec: string
  mathFormula?: string
  limitations: string
}

const PIPELINE_STAGES: PipelineStageInfo[] = [
  {
    id: 'user_message',
    title: '1. User Message Ingestion',
    category: 'TX',
    module: 'messaging/models.py & API',
    status: 'VERIFIED',
    purpose: 'Captures operator tactical payload, waypoint updates, or telemetry string.',
    inputSpec: 'Arbitrary UTF-8 Text / Tactical JSON',
    outputSpec: 'Raw Byte Array (N Bytes)',
    limitations: 'Recommended burst size < 256 bytes per packet for optimal LPI airtime.',
  },
  {
    id: 'crypto_packaging',
    title: '2. AES-256-GCM v2 Cryptography',
    category: 'TX',
    module: 'lpi_v4/lpi_crypto.py',
    status: 'VERIFIED',
    purpose: 'Provides authenticated encryption with zero plaintext leakage and anti-tamper protection.',
    inputSpec: 'Raw Bytes + 256-bit Key + 12B IV Nonce',
    outputSpec: 'Ciphertext + 16-Byte GMAC Tag (+28B Envelope)',
    mathFormula: 'C = AES_{256}(P), \\quad T = GMAC(C, Nonce)',
    limitations: 'Unique 96-bit initialization vector generated per burst.',
  },
  {
    id: 'fec_framing',
    title: '3. Reed-Solomon RS(42, 34) Framing',
    category: 'TX',
    module: 'lpi_v4/lpi_crypto.py',
    status: 'VERIFIED',
    purpose: 'Adds forward error correction parity symbols to withstand burst channel fades and noise spikes.',
    inputSpec: '34-Byte Data Blocks',
    outputSpec: '42-Byte Codewords (+8 Parity Symbols)',
    mathFormula: 't = \\lfloor(42 - 34)/2\\rfloor = 4 \\text{ Symbol Errors Corrected}',
    limitations: 'Block error if channel corrupts more than 4 symbols in a single codeword.',
  },
  {
    id: 'waveform_gen',
    title: '4. CGAN Waveform Synthesis',
    category: 'TX',
    module: 'lpi_v4/lpi_core.py (LPIGenerator)',
    status: 'VERIFIED',
    purpose: 'Transforms digital bits into a low-probability-of-intercept noise-like complex baseband waveform.',
    inputSpec: 'Latent Noise z ~ N(0, I₆₄) + 128 Bits',
    outputSpec: '512 Complex Baseband I/Q Samples',
    mathFormula: 'x = G(z, c) \\in \\mathbb{C}^{512}, \\quad \\text{Spreading Gain: } 9.03 \\text{ dB}',
    limitations: 'Requires trained generator checkpoint (lpi_v4.best.pt).',
  },
  {
    id: 'preamble_mux',
    title: '5. Zadoff-Chu Preamble Multiplexer',
    category: 'TX',
    module: 'lpi_v4/lpi_core.py',
    status: 'VERIFIED',
    purpose: 'Prepends constant-amplitude zero-autocorrelation (CAZAC) synchronization sequence.',
    inputSpec: '64-Sample ZC Sequence (Root u=29)',
    outputSpec: '576 Total Burst Samples (2.344 ms airtime)',
    mathFormula: 'p[n] = \\exp\\left(-j \\frac{\\pi u n(n+1)}{N_{zc}}\\right), \\quad N_{zc}=64, u=29',
    limitations: 'Root u=29 shared between authorized transceivers.',
  },
  {
    id: 'sdr_tx',
    title: '6. SDR Transmitter (UHD)',
    category: 'TX',
    module: 'lpi_v4/tx_usrp.py & uhd_io.py',
    status: 'HARDWARE_READY',
    purpose: 'Streams complex baseband samples to Ettus USRP B205mini FPGA DAC.',
    inputSpec: '576 Complex Float32 Samples',
    outputSpec: '2.484 GHz RF Radiation (-98 dBm PSD, 0 dB Gain)',
    limitations: 'Decimation ratio 250 from 61.44 MHz master clock (245.76 kS/s).',
  },
  {
    id: 'rf_channel',
    title: '7. Over-The-Air RF Channel',
    category: 'RF',
    module: 'Physical Space / AWGN Simulator',
    status: 'VERIFIED',
    purpose: 'Electromagnetic propagation environment with thermal noise, path loss, and frequency offsets.',
    inputSpec: 'Transmitted RF Signal (-98 dBm)',
    outputSpec: 'Received RF Signal + AWGN (-95 dBm floor)',
    mathFormula: 'y(t) = x(t) e^{j(2\\pi \\Delta f t + \\theta)} + w(t), \\quad SNR \\approx -6.0 \\text{ dB}',
    limitations: 'Signal power sits 3 dB below thermal noise floor.',
  },
  {
    id: 'sdr_rx',
    title: '8. SDR Receiver (UHD)',
    category: 'RX',
    module: 'lpi_v4/rx_usrp.py & uhd_io.py',
    status: 'HARDWARE_READY',
    purpose: 'Samples RF band at 245.76 kS/s using USRP B205mini FPGA ADC with 30 dB LNA gain.',
    inputSpec: '2.484 GHz Over-the-Air Waveform',
    outputSpec: 'Raw Discrete Complex Baseband Stream',
    limitations: 'Requires calibrated antenna matching at 2.484 GHz.',
  },
  {
    id: 'sync_corr',
    title: '9. Preamble Synchronization & CFO',
    category: 'RX',
    module: 'lpi_v4/lpi_core.py',
    status: 'VERIFIED',
    purpose: 'Correlates received stream with ZC-64 reference to locate burst boundary and estimate CFO.',
    inputSpec: 'Complex Baseband Stream',
    outputSpec: 'Burst Aligned 512-sample window + Residual CFO',
    mathFormula: 'R_{xy}[k] = \\sum_{n=0}^{63} y[n+k] p^*[n] \\ge 0.65 \\text{ Threshold}',
    limitations: 'Detects bursts down to -8 dB SNR.',
  },
  {
    id: 'manifold_inversion',
    title: '10. Neural Manifold Inversion',
    category: 'RX',
    module: 'lpi_v4/lpi_core.py (LPIDecoder)',
    status: 'VERIFIED',
    purpose: 'Inverts learned neural waveform manifold to extract soft log-likelihood ratio bits.',
    inputSpec: '512 Equalized Complex Samples',
    outputSpec: '128 Candidate Codeword Bits',
    limitations: 'Optimized for AWGN and low-CFO multipath channels.',
  },
  {
    id: 'fec_decode',
    title: '11. Reed-Solomon Decoding',
    category: 'RX',
    module: 'lpi_v4/lpi_crypto.py',
    status: 'VERIFIED',
    purpose: 'Computes Galois Field syndromes, locates error positions, and corrects symbol errors.',
    inputSpec: '42-Byte Codeword',
    outputSpec: '34-Byte Clean Data Block',
    mathFormula: 'S_i = \\sum_{j=0}^{n-1} c_j \\alpha^{ij} = 0 \\implies \\text{Clean Codeword}',
    limitations: 'Flags uncorrectable frames if errors exceed capacity.',
  },
  {
    id: 'auth_decrypt',
    title: '12. GMAC Authenticate & Decrypt',
    category: 'RX',
    module: 'lpi_v4/lpi_crypto.py',
    status: 'VERIFIED',
    purpose: 'Verifies Poly1305 GMAC tag, decrypts ciphertext, and dispatches HMAC delivery ACK.',
    inputSpec: 'Authenticated Envelope + Tag',
    outputSpec: 'Verified Plaintext Message String',
    limitations: 'Immediate rejection if tag does not match (tampering detected).',
  },
]

export const PipelineVisualizerView: React.FC = () => {
  const [selectedStageId, setSelectedStageId] = useState<string>('waveform_gen')

  const activeStage = PIPELINE_STAGES.find((s) => s.id === selectedStageId) || PIPELINE_STAGES[0]

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-zinc-900/80 border border-zinc-800 p-4 rounded-xl">
        <div className="flex items-center space-x-2">
          <Zap className="w-5 h-5 text-emerald-400" />
          <h2 className="text-base font-bold font-mono text-zinc-100">
            Interactive Communication Pipeline Visualisation
          </h2>
        </div>
        <p className="text-xs text-zinc-400 mt-0.5 font-sans">
          Click any processing stage to inspect its mathematical formulation, implementation module, inputs, and outputs
        </p>
      </div>

      {/* Interactive System Flow Diagram */}
      <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 font-mono">
          End-to-End Tactical Flowgraph
        </h3>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          {PIPELINE_STAGES.map((stage) => {
            const isSelected = stage.id === selectedStageId

            return (
              <div
                key={stage.id}
                onClick={() => setSelectedStageId(stage.id)}
                className={`p-3 rounded-lg border cursor-pointer transition-all flex flex-col justify-between h-28 ${
                  isSelected
                    ? 'bg-emerald-950/40 border-emerald-500 shadow-lg text-emerald-300'
                    : 'bg-zinc-950 border-zinc-800 hover:border-zinc-700 text-zinc-300'
                }`}
              >
                <div>
                  <span
                    className={`text-[9px] font-mono px-1 py-0.2 rounded font-semibold ${
                      stage.category === 'TX'
                        ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                        : stage.category === 'RF'
                        ? 'bg-amber-950 text-amber-400 border border-amber-800'
                        : 'bg-cyan-950 text-cyan-400 border border-cyan-800'
                    }`}
                  >
                    {stage.category}
                  </span>
                  <h4 className="text-[11px] font-bold font-mono mt-1.5 line-clamp-2 leading-tight">
                    {stage.title}
                  </h4>
                </div>

                <div className="flex items-center justify-between text-[9px] font-mono text-zinc-500 pt-1 border-t border-zinc-850">
                  <span>{stage.status}</span>
                  <CheckCircle2 className={`w-3 h-3 ${isSelected ? 'text-emerald-400' : 'text-zinc-600'}`} />
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Contextual Stage Inspector Panel */}
      <div className="bg-zinc-900/60 border border-zinc-800 p-5 rounded-xl space-y-4">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-bold font-mono text-zinc-100">
                {activeStage.title}
              </h3>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                {activeStage.status}
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-1 font-sans">{activeStage.purpose}</p>
          </div>
          <span className="text-xs font-mono text-zinc-500">
            Source: <strong>{activeStage.module}</strong>
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
          <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-850 space-y-1">
            <span className="text-zinc-500 uppercase text-[10px] block">Input Specification:</span>
            <span className="text-zinc-200">{activeStage.inputSpec}</span>
          </div>

          <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-850 space-y-1">
            <span className="text-zinc-500 uppercase text-[10px] block">Output Specification:</span>
            <span className="text-cyan-400">{activeStage.outputSpec}</span>
          </div>

          {activeStage.mathFormula && (
            <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-850 space-y-1 md:col-span-2">
              <span className="text-zinc-500 uppercase text-[10px] block">Mathematical Formulation:</span>
              <code className="text-amber-300 font-mono text-xs">{activeStage.mathFormula}</code>
            </div>
          )}

          <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-850 space-y-1 md:col-span-2">
            <span className="text-zinc-500 uppercase text-[10px] block">Operational Constraints &amp; Limitations:</span>
            <span className="text-zinc-400">{activeStage.limitations}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
