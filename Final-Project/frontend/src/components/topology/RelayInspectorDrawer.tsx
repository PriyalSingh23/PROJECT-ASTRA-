import React, { useState } from 'react'
import {
  X,
  Radio,
  Battery,
  AlertTriangle,
  RotateCcw,
  Zap,
  Thermometer,
  Layers,
  Activity,
  Compass,
  HardDrive,
  ShieldAlert,
} from 'lucide-react'
import { TopoRelay, TopoLink } from './model'
import { api } from '../../services/api'

interface RelayInspectorDrawerProps {
  relay: TopoRelay | null
  links: TopoLink[]
  onClose: () => void
  onRefresh: () => void
  onNotify?: (message: string) => void
}

export const RelayInspectorDrawer: React.FC<RelayInspectorDrawerProps> = ({
  relay,
  links,
  onClose,
  onRefresh,
  onNotify,
}) => {
  const [loadingAction, setLoadingAction] = useState<string | null>(null)

  if (!relay) return null

  // Find connected links for this relay
  const connectedLinks = links.filter(
    (l) => l.sourceId === relay.id || l.targetId === relay.id
  )

  const handleApplyOverride = async (action: string, telemetry: {
    status?: string
    battery?: number
    storage_pct?: number
    queue_depth?: number
  }) => {
    setLoadingAction(action)
    try {
      await api.setRelayTelemetry(relay.id, telemetry)
      const notice = `Applied override [${action}] to ${relay.label} (${relay.id})`
      if (onNotify) {
        onNotify(notice)
      }
      onRefresh()
    } catch (err) {
      if (onNotify) {
        onNotify(`Failed to apply override to ${relay.id}: ${String(err)}`)
      }
    } finally {
      setLoadingAction(null)
    }
  }

  // Visual status pill colors
  const getStatusBadge = (status: string, cutoff: boolean) => {
    if (cutoff) {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-950/80 text-rose-300 border border-rose-600/60 animate-pulse">
          FAILSAFE CUTOFF
        </span>
      )
    }
    switch (status) {
      case 'ONLINE':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950/80 text-emerald-300 border border-emerald-600/60">
            ONLINE
          </span>
        )
      case 'RF_JAMMED':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-950/80 text-rose-300 border border-rose-600/60 animate-pulse">
            RF JAMMED
          </span>
        )
      case 'FORCE_OFFLINE':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-red-950/80 text-red-300 border border-red-600/60">
            FORCE OFFLINE
          </span>
        )
      case 'LOW_BATTERY':
      case 'BATTERY_CRITICAL':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-950/80 text-amber-300 border border-amber-600/60 animate-pulse">
            LOW BATTERY
          </span>
        )
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-zinc-800 text-zinc-300 border border-zinc-700">
            {status}
          </span>
        )
    }
  }

  // Battery bar color
  const batteryPct = relay.battery
  const batteryColor =
    batteryPct > 50
      ? 'bg-emerald-500'
      : batteryPct > 15
      ? 'bg-amber-500'
      : 'bg-rose-500 animate-pulse'

  // Estimated voltage: 10.0V + (battery / 100) * 4.2V
  const estimatedVoltage = (10.0 + (batteryPct / 100) * 4.2).toFixed(1)

  // Elevation km: Y * 2.5 km
  const elevationKm = (relay.position[1] * 2.5).toFixed(1)

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-96 bg-white/95 dark:bg-zinc-950/95 border-l border-slate-200 dark:border-zinc-800 backdrop-blur-md shadow-2xl flex flex-col text-slate-800 dark:text-zinc-200">
      {/* Header */}
      <div className="p-4 border-b border-slate-200 dark:border-zinc-800 flex items-start justify-between bg-slate-50 dark:bg-zinc-900/40">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 rounded bg-cyan-100 dark:bg-cyan-950/50 border border-cyan-300 dark:border-cyan-800/60 text-cyan-700 dark:text-cyan-400">
            <Radio className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-mono font-bold text-slate-900 dark:text-zinc-100 tracking-wide">
                {relay.label}
              </h3>
              {getStatusBadge(relay.status, relay.failsafeCutoff)}
            </div>
            <div className="flex items-center space-x-2 mt-0.5 text-[10px] font-mono text-slate-500 dark:text-zinc-400">
              <span>{relay.id}</span>
              <span>·</span>
              <span className="text-cyan-400">{relay.sector}</span>
            </div>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors"
          title="Close Inspector"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Scrollable Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs font-mono">
        {/* Spatial Coordinates & Altitude */}
        <div className="p-3 rounded-lg border border-zinc-800 bg-zinc-900/30 space-y-2">
          <div className="flex items-center justify-between text-[11px] text-zinc-400">
            <span className="flex items-center space-x-1">
              <Compass className="w-3.5 h-3.5 text-cyan-400" />
              <span>THEATER COORDINATES</span>
            </span>
            <span className="text-zinc-500">1 unit = 2.5 km</span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="bg-zinc-950 border border-zinc-800/80 rounded p-1.5">
              <div className="text-[10px] text-zinc-500">X (EAST/WEST)</div>
              <div className="text-xs font-bold text-zinc-200">
                {relay.position[0] > 0 ? `+${relay.position[0].toFixed(1)}` : relay.position[0].toFixed(1)}
              </div>
            </div>
            <div className="bg-zinc-950 border border-zinc-800/80 rounded p-1.5">
              <div className="text-[10px] text-cyan-400">Y (ALTITUDE)</div>
              <div className="text-xs font-bold text-cyan-300">
                {relay.position[1].toFixed(1)} ({elevationKm} km)
              </div>
            </div>
            <div className="bg-zinc-950 border border-zinc-800/80 rounded p-1.5">
              <div className="text-[10px] text-zinc-500">Z (NORTH/SOUTH)</div>
              <div className="text-xs font-bold text-zinc-200">
                {relay.position[2] > 0 ? `+${relay.position[2].toFixed(1)}` : relay.position[2].toFixed(1)}
              </div>
            </div>
          </div>
        </div>

        {/* Telemetry Health Gauges */}
        <div className="p-3 rounded-lg border border-zinc-800 bg-zinc-900/30 space-y-3">
          <div className="flex items-center justify-between text-[11px] text-zinc-400">
            <span className="flex items-center space-x-1">
              <Activity className="w-3.5 h-3.5 text-emerald-400" />
              <span>SUBSYSTEM TELEMETRY</span>
            </span>
            <span className="text-[10px] text-zinc-500">POLL: 2.0s</span>
          </div>

          {/* Battery Health */}
          <div className="space-y-1">
            <div className="flex justify-between text-[10px]">
              <span className="flex items-center space-x-1 text-zinc-400">
                <Battery className="w-3 h-3 text-emerald-400" />
                <span>BATTERY LEVEL</span>
              </span>
              <span className="font-bold text-zinc-200">
                {batteryPct}% ({estimatedVoltage}V DC)
              </span>
            </div>
            <div className="w-full bg-zinc-800 h-2 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-300 ${batteryColor}`}
                style={{ width: `${Math.min(100, Math.max(0, batteryPct))}%` }}
              />
            </div>
          </div>

          {/* Storage Buffer */}
          <div className="space-y-1">
            <div className="flex justify-between text-[10px]">
              <span className="flex items-center space-x-1 text-zinc-400">
                <HardDrive className="w-3 h-3 text-cyan-400" />
                <span>STORAGE BUFFER</span>
              </span>
              <span className="font-bold text-zinc-200">{relay.storage}%</span>
            </div>
            <div className="w-full bg-zinc-800 h-2 rounded-full overflow-hidden">
              <div
                className="bg-cyan-500 h-full transition-all duration-300"
                style={{ width: `${Math.min(100, Math.max(0, relay.storage))}%` }}
              />
            </div>
          </div>

          {/* Queue & Ambient Readings */}
          <div className="grid grid-cols-2 gap-2 pt-1">
            <div className="bg-zinc-950 border border-zinc-800/80 rounded p-2 flex items-center justify-between">
              <span className="text-[10px] text-zinc-500 flex items-center space-x-1">
                <Layers className="w-3 h-3 text-amber-400" />
                <span>QUEUE</span>
              </span>
              <span className="text-xs font-bold text-amber-300">{relay.queueDepth} pkts</span>
            </div>
            <div className="bg-zinc-950 border border-zinc-800/80 rounded p-2 flex items-center justify-between">
              <span className="text-[10px] text-zinc-500 flex items-center space-x-1">
                <Thermometer className="w-3 h-3 text-rose-400" />
                <span>TEMP</span>
              </span>
              <span className="text-xs font-bold text-zinc-200">32.4°C</span>
            </div>
          </div>
        </div>

        {/* Connected RF Neighbors */}
        <div className="p-3 rounded-lg border border-zinc-800 bg-zinc-900/30 space-y-2">
          <div className="text-[11px] text-zinc-400 flex items-center justify-between">
            <span>CONNECTED RF NEIGHBORS ({connectedLinks.length})</span>
            <span className="text-[9px] text-zinc-500">LINE-OF-SIGHT</span>
          </div>

          {connectedLinks.length === 0 ? (
            <div className="text-[10px] text-zinc-500 italic py-1">No adjacent RF links detected</div>
          ) : (
            <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
              {connectedLinks.map((l, idx) => {
                const neighborId = l.sourceId === relay.id ? l.targetId : l.sourceId
                return (
                  <div
                    key={idx}
                    className={`flex items-center justify-between p-2 rounded border text-[10px] ${
                      l.isBroken
                        ? 'border-rose-900/60 bg-rose-950/20 text-rose-300 line-through'
                        : l.isActiveRoute
                        ? 'border-cyan-500/50 bg-cyan-950/30 text-cyan-200 font-bold'
                        : 'border-zinc-800 bg-zinc-950/60 text-zinc-300'
                    }`}
                  >
                    <div className="flex items-center space-x-1.5 truncate">
                      <span className={l.isActiveRoute ? 'text-cyan-400' : 'text-zinc-400'}>
                        {neighborId}
                      </span>
                      {l.isActiveRoute && (
                        <span className="text-[8px] px-1 py-0.2 rounded bg-cyan-500/20 border border-cyan-500/50 text-cyan-300 font-normal">
                          ACTIVE
                        </span>
                      )}
                    </div>
                    <div className="flex items-center space-x-2 text-[9px] shrink-0 font-mono">
                      <span>{l.distanceKm.toFixed(1)} km</span>
                      <span className="text-zinc-500">·</span>
                      <span className="text-zinc-400">{l.rfTier}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Operator Impairment Override Controls (D-13) */}
        <div className="p-3 rounded-lg border border-zinc-800 bg-zinc-900/40 space-y-2.5">
          <div className="flex items-center space-x-1.5 text-[11px] text-amber-400 font-bold">
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>OPERATOR IMPAIRMENT CONTROLS</span>
          </div>
          <p className="text-[10px] text-zinc-400">
            Inject synthetic faults or recover node state. Routing engine converges in &lt; 300ms.
          </p>

          <div className="grid grid-cols-1 gap-1.5 pt-1">
            {/* Toggle Online / Recover */}
            <button
              onClick={() => handleApplyOverride('RECOVER_ONLINE', { status: 'ONLINE', battery: 95.0, queue_depth: 0 })}
              disabled={loadingAction !== null}
              className="w-full px-3 py-1.5 rounded bg-emerald-950/60 hover:bg-emerald-900/80 border border-emerald-600/60 text-emerald-300 text-[11px] font-bold transition-all flex items-center justify-center space-x-1.5 cursor-pointer disabled:opacity-50"
            >
              <RotateCcw className="w-3 h-3 text-emerald-400" />
              <span>Restore Nominal (Online • 95% Batt)</span>
            </button>

            {/* Force Offline */}
            <button
              onClick={() => handleApplyOverride('FORCE_OFFLINE', { status: 'FORCE_OFFLINE' })}
              disabled={loadingAction !== null}
              className="w-full px-3 py-1.5 rounded bg-red-950/60 hover:bg-red-900/80 border border-red-600/60 text-red-300 text-[11px] font-bold transition-all flex items-center justify-center space-x-1.5 cursor-pointer disabled:opacity-50"
            >
              <X className="w-3 h-3 text-red-400" />
              <span>Force Offline (Manual Shutdown)</span>
            </button>

            {/* Simulate Jamming */}
            <button
              onClick={() => handleApplyOverride('SIMULATE_JAMMING', { status: 'RF_JAMMED' })}
              disabled={loadingAction !== null}
              className="w-full px-3 py-1.5 rounded bg-rose-950/60 hover:bg-rose-900/80 border border-rose-600/60 text-rose-300 text-[11px] font-bold transition-all flex items-center justify-center space-x-1.5 cursor-pointer disabled:opacity-50"
            >
              <AlertTriangle className="w-3 h-3 text-rose-400" />
              <span>Simulate RF Jamming (EW Hostile)</span>
            </button>

            {/* Drain Battery (<10%) */}
            <button
              onClick={() => handleApplyOverride('DRAIN_BATTERY', { battery: 8.0, status: 'LOW_BATTERY' })}
              disabled={loadingAction !== null}
              className="w-full px-3 py-1.5 rounded bg-amber-950/60 hover:bg-amber-900/80 border border-amber-600/60 text-amber-300 text-[11px] font-bold transition-all flex items-center justify-center space-x-1.5 cursor-pointer disabled:opacity-50"
            >
              <Zap className="w-3 h-3 text-amber-400" />
              <span>Drain Battery to 8.0% (Triggers Reroute)</span>
            </button>

            {/* Failsafe Cutoff (<5%) */}
            <button
              onClick={() => handleApplyOverride('FAILSAFE_CUTOFF', { battery: 4.0, status: 'FORCE_OFFLINE' })}
              disabled={loadingAction !== null}
              className="w-full px-3 py-1.5 rounded bg-rose-950/90 hover:bg-rose-900 border border-rose-500 text-rose-200 text-[11px] font-bold transition-all flex items-center justify-center space-x-1.5 cursor-pointer disabled:opacity-50"
            >
              <ShieldAlert className="w-3 h-3 text-rose-400" />
              <span>Failsafe Cutoff (&lt; 5% Battery Lockout)</span>
            </button>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-zinc-800 bg-zinc-900/60 text-[10px] text-zinc-500 flex items-center justify-between">
        <span>SHADOWCOMM Ad-Hoc Protocol v4</span>
        <button
          onClick={onClose}
          className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors"
        >
          Close Drawer
        </button>
      </div>
    </div>
  )
}
export default RelayInspectorDrawer
