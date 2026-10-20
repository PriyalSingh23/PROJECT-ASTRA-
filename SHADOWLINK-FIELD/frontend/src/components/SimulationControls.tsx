import React, { useState } from 'react'
import {
  Wifi,
  WifiOff,
  Sliders,
  AlertTriangle,
  RotateCcw,
  Zap,
  TrendingDown,
  Activity,
} from 'lucide-react'
import { QueueStats } from '../types'
import { api } from '../services/api'

interface SimulationControlsProps {
  queueStats: QueueStats | null
  onConfigChange: () => void
}

export const SimulationControls: React.FC<SimulationControlsProps> = ({
  queueStats,
  onConfigChange,
}) => {
  const transport = queueStats?.transport
  const isOnline = transport?.is_online ?? true
  const latency = transport?.latency_ms ?? 50
  const packetDrop = Math.round((transport?.packet_drop_rate ?? 0) * 100)
  const ackDrop = Math.round((transport?.ack_drop_rate ?? 0) * 100)

  const [loading, setLoading] = useState(false)

  const handleToggleOnline = async () => {
    setLoading(true)
    try {
      await api.configureSimulation({ is_online: !isOnline })
      onConfigChange()
    } catch (err) {
      console.error('Failed to toggle simulation online status', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSliderChange = async (key: 'latency_ms' | 'packet_drop_rate' | 'ack_drop_rate', val: number) => {
    try {
      await api.configureSimulation({ [key]: val })
      onConfigChange()
    } catch (err) {
      console.error(`Failed to update ${key}`, err)
    }
  }

  const handleFault = async (faultType: string) => {
    setLoading(true)
    try {
      await api.injectFault(faultType)
      onConfigChange()
    } catch (err) {
      console.error(`Failed to inject fault ${faultType}`, err)
    } finally {
      setLoading(false)
    }
  }

  const metrics = transport?.metrics || {
    packets_sent: 0,
    packets_delivered: 0,
    acks_sent: 0,
    acks_delivered: 0,
    packets_dropped: 0,
    acks_dropped: 0,
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-lg mb-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
            <Sliders className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-100 uppercase tracking-wider font-mono flex items-center gap-2">
              Virtual RF Transport Controls
              <span className="text-[11px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono font-normal">
                Deterministic Link Emulator
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              Simulate real-world RF disconnects, packet corruption, latency, and dropped ACKs between Endpoint A and B.
            </p>
          </div>
        </div>

        {/* Link Status Toggle */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleToggleOnline}
            disabled={loading}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-mono text-xs font-semibold tracking-wider transition shadow-sm ${
              isOnline
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-500/30'
                : 'bg-rose-500/20 text-rose-300 border border-rose-500/40 hover:bg-rose-500/30'
            }`}
          >
            {isOnline ? (
              <>
                <Wifi className="w-4 h-4 text-emerald-400" />
                <span>LINK: ONLINE (HEALTHY)</span>
              </>
            ) : (
              <>
                <WifiOff className="w-4 h-4 text-rose-400 animate-pulse" />
                <span>LINK: SEVERED (OFFLINE)</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Sliders & Fault Injection */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4">
        {/* Latency Slider */}
        <div className="space-y-2">
          <div className="flex justify-between text-xs font-mono">
            <span className="text-slate-400">Channel Latency:</span>
            <span className="text-cyan-400 font-bold">{latency} ms</span>
          </div>
          <input
            type="range"
            min="0"
            max="1500"
            step="50"
            value={latency}
            onChange={(e) => handleSliderChange('latency_ms', Number(e.target.value))}
            className="w-full accent-cyan-500 bg-slate-800 rounded-lg cursor-pointer h-2"
          />
          <div className="flex justify-between text-[10px] text-slate-500 font-mono">
            <span>0 ms (Fiber/LAN)</span>
            <span>500 ms (Tactical RF)</span>
            <span>1500 ms (Satellite)</span>
          </div>
        </div>

        {/* Packet Loss Slider */}
        <div className="space-y-2">
          <div className="flex justify-between text-xs font-mono">
            <span className="text-slate-400">Forward Packet Drop Rate:</span>
            <span className={`font-bold ${packetDrop > 0 ? 'text-amber-400' : 'text-slate-300'}`}>
              {packetDrop}%
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            value={packetDrop}
            onChange={(e) => handleSliderChange('packet_drop_rate', Number(e.target.value) / 100)}
            className="w-full accent-amber-500 bg-slate-800 rounded-lg cursor-pointer h-2"
          />
          <div className="flex justify-between text-[10px] text-slate-500 font-mono">
            <span>0% Clean</span>
            <span>50% Degradation</span>
            <span>100% Jammed</span>
          </div>
        </div>

        {/* ACK Loss Slider */}
        <div className="space-y-2">
          <div className="flex justify-between text-xs font-mono">
            <span className="text-slate-400">Return ACK Drop Rate:</span>
            <span className={`font-bold ${ackDrop > 0 ? 'text-rose-400' : 'text-slate-300'}`}>
              {ackDrop}%
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            value={ackDrop}
            onChange={(e) => handleSliderChange('ack_drop_rate', Number(e.target.value) / 100)}
            className="w-full accent-rose-500 bg-slate-800 rounded-lg cursor-pointer h-2"
          />
          <div className="flex justify-between text-[10px] text-slate-500 font-mono">
            <span>0% Nominal</span>
            <span>50% Asymmetric</span>
            <span>100% Lost ACKs</span>
          </div>
        </div>
      </div>

      {/* Preset Action Buttons & Telemetry Bar */}
      <div className="mt-4 pt-3 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3">
        {/* Quick Fault Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-mono text-slate-400">Quick Scenarios:</span>
          <button
            onClick={() => handleFault('sever_link')}
            disabled={loading}
            className="px-2.5 py-1 text-xs font-mono rounded bg-rose-950/60 border border-rose-800/60 text-rose-300 hover:bg-rose-900/60 transition flex items-center gap-1"
          >
            <Zap className="w-3 h-3" />
            Cut Connection
          </button>
          <button
            onClick={() => handleFault('restore_link')}
            disabled={loading}
            className="px-2.5 py-1 text-xs font-mono rounded bg-emerald-950/60 border border-emerald-800/60 text-emerald-300 hover:bg-emerald-900/60 transition flex items-center gap-1"
          >
            <Activity className="w-3 h-3" />
            Restore Link
          </button>
          <button
            onClick={() => handleFault('drop_acks')}
            disabled={loading}
            className="px-2.5 py-1 text-xs font-mono rounded bg-amber-950/60 border border-amber-800/60 text-amber-300 hover:bg-amber-900/60 transition flex items-center gap-1"
          >
            <TrendingDown className="w-3 h-3" />
            Sever Return ACKs (50%)
          </button>
          <button
            onClick={() => handleFault('reset_transport')}
            disabled={loading}
            className="px-2.5 py-1 text-xs font-mono rounded bg-slate-800 border border-slate-700 text-slate-300 hover:bg-slate-700 transition flex items-center gap-1"
          >
            <RotateCcw className="w-3 h-3" />
            Reset Nominal
          </button>
        </div>

        {/* Telemetry Numbers */}
        <div className="flex items-center gap-4 text-xs font-mono text-slate-400">
          <div className="flex items-center gap-1">
            <span className="text-slate-500">Sent:</span>
            <span className="text-slate-200 font-bold">{metrics.packets_sent}</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-slate-500">Delivered:</span>
            <span className="text-emerald-400 font-bold">{metrics.packets_delivered}</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-slate-500">Pkts Dropped:</span>
            <span className="text-amber-400 font-bold">{metrics.packets_dropped}</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-slate-500">ACKs Delivered:</span>
            <span className="text-cyan-400 font-bold">{metrics.acks_delivered}</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-slate-500">ACKs Dropped:</span>
            <span className="text-rose-400 font-bold">{metrics.acks_dropped}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
