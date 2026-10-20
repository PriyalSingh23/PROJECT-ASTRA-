import React, { useEffect, useState } from 'react'
import {
  Radio,
  ShieldAlert,
  ShieldCheck,
  Cpu,
  Layers,
  AlertTriangle,
  CheckCircle,
  Activity,
  Lock,
  Flame,
  Terminal,
} from 'lucide-react'
import { AdapterStatus } from '../types'
import { api } from '../services/api'

export const InteroperabilityConsole: React.FC = () => {
  const [adapters, setAdapters] = useState<AdapterStatus[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchAdapters = async () => {
    setLoading(true)
    try {
      const data = await api.getAdapters()
      setAdapters(data)
    } catch (err: any) {
      setError(err.message || 'Failed to load adapters')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAdapters()
  }, [])

  return (
    <div className="space-y-6">
      {/* Overview Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
        <div className="flex items-center gap-3 pb-3 border-b border-slate-800">
          <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-100 uppercase tracking-wider font-mono">
              Radio Interoperability Gateways & Transports
            </h2>
            <p className="text-xs text-slate-400">
              Approved hardware adapters, safety locks, and software research interfaces registered with the Gateway Router.
            </p>
          </div>
        </div>

        {/* Safety Policy Alert */}
        <div className="mt-4 p-3.5 bg-amber-950/30 border border-amber-800/60 rounded-lg flex items-start gap-3 text-xs font-mono text-amber-300">
          <ShieldAlert className="w-5 h-5 flex-shrink-0 text-amber-400 mt-0.5" />
          <div className="space-y-1">
            <span className="font-bold uppercase tracking-wider">
              HARDWARE SAFETY ENFORCEMENT POLICY
            </span>
            <p className="text-[11px] text-amber-200/80 leading-relaxed">
              Physical RF emissions are strictly prohibited in uncertified test environments. Real radio adapters (Motorola / STAR-V / SDR) enforce profile-specific safety lockouts and report honest readiness states. Only verified simulated transports or approved hardware profiles are permitted to route field packets.
            </p>
          </div>
        </div>
      </div>

      {/* Adapters Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {adapters.map((adapter) => {
          const isLockedOut = adapter.safety_lockout_active || adapter.state === 'LOCKED_OUT'
          const isReady = adapter.state === 'READY'

          return (
            <div
              key={adapter.adapter_id}
              className={`bg-slate-900 border rounded-xl p-5 shadow-xl flex flex-col justify-between ${
                isLockedOut
                  ? 'border-rose-900/40 bg-gradient-to-b from-rose-950/10 to-slate-900'
                  : isReady
                  ? 'border-emerald-900/40 bg-gradient-to-b from-emerald-950/10 to-slate-900'
                  : 'border-slate-800'
              }`}
            >
              <div>
                {/* Header */}
                <div className="flex items-start justify-between pb-3 border-b border-slate-800">
                  <div className="flex items-center gap-2.5">
                    <div
                      className={`p-2 rounded-lg ${
                        isLockedOut
                          ? 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                          : isReady
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                          : 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
                      }`}
                    >
                      {isLockedOut ? (
                        <Lock className="w-5 h-5" />
                      ) : (
                        <Radio className="w-5 h-5" />
                      )}
                    </div>
                    <div>
                      <h3 className="font-mono font-bold text-slate-100 text-sm">
                        {adapter.adapter_name}
                      </h3>
                      <span className="text-[10px] font-mono text-slate-400">
                        ID: {adapter.adapter_id} | v{adapter.version}
                      </span>
                    </div>
                  </div>

                  {/* State badge */}
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${
                      isLockedOut
                        ? 'bg-rose-950 text-rose-300 border-rose-800'
                        : isReady
                        ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                        : 'bg-slate-800 text-slate-300 border-slate-700'
                    }`}
                  >
                    {adapter.state}
                  </span>
                </div>

                {/* Description */}
                <p className="mt-3 text-xs text-slate-300 font-mono leading-relaxed">
                  {adapter.description}
                </p>

                {/* Supported Capabilities */}
                <div className="mt-4">
                  <span className="text-[10px] uppercase font-mono text-slate-500 block mb-1.5">
                    Declared Capabilities
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {adapter.supported_features.map((feat) => (
                      <span
                        key={feat}
                        className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-950 border border-slate-800 text-slate-300"
                      >
                        {feat}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Telemetry / Metrics */}
                {adapter.metrics && Object.keys(adapter.metrics).length > 0 && (
                  <div className="mt-4 p-3 bg-slate-950 rounded-lg border border-slate-800 text-[11px] font-mono">
                    <span className="text-slate-500 block text-[10px] uppercase mb-1">
                      Adapter Telemetry & Operational State
                    </span>
                    <div className="grid grid-cols-2 gap-2 text-slate-300">
                      {Object.entries(adapter.metrics).map(([k, v]) => (
                        <div key={k}>
                          <span className="text-slate-500 text-[10px] block">{k}:</span>
                          <span className="text-slate-200 font-semibold">
                            {typeof v === 'boolean' ? (v ? 'TRUE' : 'FALSE') : String(v)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Footer Safety Indicator */}
              <div className="mt-5 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono">
                <div className="flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5 text-slate-500" />
                  <span className="text-slate-400">RF Emission:</span>
                  <span
                    className={`font-bold ${
                      adapter.is_transmitting_rf
                        ? 'text-rose-400'
                        : 'text-emerald-400'
                    }`}
                  >
                    {adapter.is_transmitting_rf ? 'ACTIVE' : 'LOCKED (SAFE)'}
                  </span>
                </div>

                <div className="flex items-center gap-1.5">
                  <span className="text-slate-500">Hardware:</span>
                  <span
                    className={`font-semibold ${
                      adapter.is_hardware_connected
                        ? 'text-emerald-400'
                        : 'text-slate-400'
                    }`}
                  >
                    {adapter.is_hardware_connected ? 'CONNECTED' : 'STANDBY / VIRTUAL'}
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
