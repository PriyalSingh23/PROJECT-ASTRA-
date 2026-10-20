import React, { useState, useEffect, useCallback } from 'react'
import {
  Layers,
  Radio,
  ShieldAlert,
  ShieldCheck,
  CheckCircle,
  AlertCircle,
  Cpu,
  Lock,
  HardDrive,
  RotateCcw,
  Battery,
  Thermometer,
  Plane,
  RefreshCw,
  ArrowRightLeft,
  Activity,
  Zap,
} from 'lucide-react'
import { Endpoint, TransportAdapter, RelayNode } from '../types'
import { api } from '../services/api'
import { StarVLockoutDossierModal } from './StarVLockoutDossierModal'

interface DevicesViewProps {
  endpoints: Endpoint[]
  onRefresh: () => void
}

interface ActiveTransportInfo {
  active_transport: string | null
  mode: string
  is_live: boolean
  auto_failover: boolean
  bridge?: any
}

const TRANSPORT_LABELS: Record<string, string> = {
  simulated_link: 'Simulated Link (In-Process RF)',
  motorola_dmr: 'Motorola MOTOTRBO (TMS / XCMP)',
  starv_sdr: 'STAR-V Tactical SDR (LOCKED OUT)',
  lpi_cgan: 'LPI-CGAN Neural Transceiver (Research)',
}

export const DevicesView: React.FC<DevicesViewProps> = ({ endpoints, onRefresh }) => {
  const [transports, setTransports] = useState<TransportAdapter[]>([])
  const [activeTransportInfo, setActiveTransportInfo] = useState<ActiveTransportInfo | null>(null)
  const [relays, setRelays] = useState<RelayNode[]>([])
  const [loading, setLoading] = useState<boolean>(true)
  const [isStarVModalOpen, setIsStarVModalOpen] = useState<boolean>(false)
  const [updatingRelayId, setUpdatingRelayId] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    try {
      const [transportsData, activeData, relaysData] = await Promise.all([
        api.getTransports(),
        api.getActiveTransport(),
        api.getRelays(),
      ])
      setTransports(transportsData)
      setActiveTransportInfo(activeData)
      setRelays(relaysData)
    } catch (err) {
      console.warn('Could not load devices/transports data:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleTransportChange = async (transportId: string) => {
    try {
      await api.setActiveTransport(transportId, activeTransportInfo?.auto_failover ?? true)
      await loadData()
      onRefresh()
    } catch (err) {
      console.error('Failed to change active transport:', err)
    }
  }

  const handleFailoverToggle = async () => {
    const current = activeTransportInfo?.auto_failover ?? true
    try {
      const res = await api.setAutoFailover(!current)
      setActiveTransportInfo((prev) =>
        prev ? { ...prev, auto_failover: res.auto_failover } : null
      )
    } catch (err) {
      console.error('Failed to toggle auto-failover:', err)
    }
  }

  const handleSimulateRelayLowBattery = async (relayId: string) => {
    setUpdatingRelayId(relayId)
    try {
      await api.updateRelayTelemetry(relayId, { battery: 4.0 })
      await loadData()
    } catch (err) {
      console.error('Failed to simulate low battery:', err)
    } finally {
      setUpdatingRelayId(null)
    }
  }

  const handleSimulateRelayStorageFull = async (relayId: string) => {
    setUpdatingRelayId(relayId)
    try {
      await api.updateRelayTelemetry(relayId, { storage_pct: 99.0 })
      await loadData()
    } catch (err) {
      console.error('Failed to simulate storage full:', err)
    } finally {
      setUpdatingRelayId(null)
    }
  }

  const handleResetRelay = async (relayId: string) => {
    setUpdatingRelayId(relayId)
    try {
      await api.resetRelayTelemetry(relayId)
      await loadData()
    } catch (err) {
      console.error('Failed to reset relay telemetry:', err)
    } finally {
      setUpdatingRelayId(null)
    }
  }

  // Determine active route status badge
  const activeTransportId = activeTransportInfo?.active_transport || 'simulated_link'
  const isAutoFailover = activeTransportInfo?.auto_failover ?? true
  const isRouteLockedOut = activeTransportId === 'starv_sdr'
  const activeAdapter = transports.find((t) => t.transport_id === activeTransportId)
  const isRouteUnavailable =
    !isAutoFailover &&
    (isRouteLockedOut ||
      activeAdapter?.readiness === 'LOCKED_OUT' ||
      activeAdapter?.connection_state === 'OFFLINE')

  const activeRouteName =
    TRANSPORT_LABELS[activeTransportId] ||
    activeAdapter?.display_name ||
    activeTransportId

  return (
    <div className="max-w-7xl w-full mx-auto space-y-6">
      {/* Overview Header */}
      <div className="bg-zinc-900/80 border border-zinc-800 p-4 rounded-xl flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold font-mono text-zinc-100 flex items-center space-x-2">
            <Layers className="w-5 h-5 text-emerald-400" />
            <span>Devices, Multi-Transport Broker & Tactical Gateways</span>
          </h2>
          <p className="text-xs text-zinc-400 font-sans mt-0.5">
            Configured stations, active transport routing, hardware safety lockout, and store-and-forward relays
          </p>
        </div>
        <button
          onClick={() => {
            setLoading(true)
            loadData()
          }}
          disabled={loading}
          className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-zinc-100 font-mono text-xs flex items-center space-x-1.5 transition-colors cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Transport Routing Control Panel (D-01, D-02, T-04-01) */}
      <div className="bg-[#131B2E] border border-cyan-900/60 p-4 rounded-xl space-y-4 shadow-[0_4px_20px_rgba(0,0,0,0.5)]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <span className="text-[10px] font-mono text-cyan-400 font-bold uppercase tracking-wider flex items-center space-x-1">
              <ArrowRightLeft className="w-3.5 h-3.5" />
              <span>Tactical Multi-Transport Broker Routing</span>
            </span>
            <div className="flex items-center space-x-2">
              {isRouteUnavailable ? (
                <span className="px-2.5 py-1 rounded bg-rose-950/80 border border-rose-500/80 text-rose-300 text-xs font-mono font-bold shadow-[0_0_12px_rgba(244,63,94,0.3)] animate-pulse">
                  ROUTE_UNAVAILABLE (HOLDING IN QUEUE)
                </span>
              ) : (
                <span className="px-2.5 py-1 rounded bg-cyan-950/80 border border-cyan-500/70 text-cyan-300 text-xs font-mono font-bold shadow-[0_0_12px_rgba(6,182,212,0.2)]">
                  ACTIVE ROUTE: {activeRouteName}
                </span>
              )}
            </div>
          </div>

          {/* Auto-Failover Toggle Switch */}
          <div className="flex items-center space-x-3">
            <button
              type="button"
              onClick={handleFailoverToggle}
              className={`px-3 py-1.5 rounded-lg font-mono text-xs font-bold border transition-all cursor-pointer flex items-center space-x-2 ${
                isAutoFailover
                  ? 'bg-emerald-950/70 border-emerald-500/80 text-emerald-300 shadow-[0_0_10px_rgba(16,185,129,0.2)]'
                  : 'bg-amber-950/70 border-amber-500/80 text-amber-300 shadow-[0_0_10px_rgba(245,158,11,0.2)]'
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isAutoFailover ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
                }`}
              />
              <span>
                {isAutoFailover
                  ? 'AUTO-FAILOVER: ENABLED'
                  : 'AUTO-FAILOVER: DISABLED (STRICT PINNING)'}
              </span>
            </button>
          </div>
        </div>

        {/* Route Selector Dropdown & Info */}
        <div className="pt-3 border-t border-zinc-800/80 flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
          <div className="flex items-center space-x-2">
            <span className="text-zinc-400">Select Pinned Route:</span>
            <select
              value={activeTransportId}
              onChange={(e) => handleTransportChange(e.target.value)}
              className="bg-[#0B0F17] border border-zinc-700 rounded-lg px-3 py-1.5 text-xs text-zinc-100 font-mono focus:outline-none focus:border-cyan-500 cursor-pointer"
            >
              <option value="simulated_link">Simulated Link (In-Process RF)</option>
              <option value="motorola_dmr">Motorola MOTOTRBO (TMS / XCMP)</option>
              <option value="starv_sdr">STAR-V Tactical SDR (LOCKED OUT)</option>
              <option value="lpi_cgan">LPI-CGAN Neural Transceiver (Research)</option>
            </select>
          </div>
          <div className="text-[11px] text-zinc-400">
            {isAutoFailover ? (
              <span className="text-emerald-400">
                ✓ Failover route active: Automatically routes through operational adapters on outage
              </span>
            ) : (
              <span className="text-amber-400">
                ⚠ Strict Pinning: Outbound messages held in queue with ROUTE_UNAVAILABLE if pinned route fails
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Section 1: Configured Station Endpoints */}
      <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 font-mono">
          Configured Station Endpoints ({endpoints.length})
        </h3>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-500 uppercase text-[10px]">
                <th className="py-2.5">Endpoint ID</th>
                <th className="py-2.5">Display Name</th>
                <th className="py-2.5">Type</th>
                <th className="py-2.5">Authentication</th>
                <th className="py-2.5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/40 text-zinc-300">
              {endpoints.map((ep) => (
                <tr key={ep.endpoint_id} className="hover:bg-zinc-850/40">
                  <td className="py-2.5 font-bold text-emerald-400">{ep.endpoint_id}</td>
                  <td className="py-2.5 font-sans font-medium text-zinc-100">{ep.display_name}</td>
                  <td className="py-2.5 text-zinc-400">{ep.endpoint_type}</td>
                  <td className="py-2.5">
                    <span className="px-2 py-0.5 rounded bg-emerald-950/40 text-emerald-300 border border-emerald-800 text-[10px]">
                      Pre-Shared Token Verified
                    </span>
                  </td>
                  <td className="py-2.5">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        ep.enabled
                          ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                          : 'bg-zinc-800 text-zinc-500'
                      }`}
                    >
                      {ep.enabled ? 'ACTIVE' : 'DISABLED'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Section 2: Radio Interoperability Adapters */}
      <div className="space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 font-mono">
          Radio Adapters & Hardware Boundary Isolation
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Motorola MOTOTRBO Adapter */}
          <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-zinc-500 uppercase">Motorola Solutions</span>
                <span className="px-2 py-0.5 rounded bg-sky-950/60 text-sky-400 border border-sky-800 text-[10px] font-mono font-bold">
                  SIMULATION ONLY
                </span>
              </div>
              <h4 className="text-sm font-bold font-mono text-zinc-100">
                MOTOTRBO / APX TMS Adapter
              </h4>
              <p className="text-xs text-zinc-400 font-sans leading-relaxed">
                Text Messaging Service (TMS) over XCMP protocol. Enforces strict 280-byte DMR maximum packet limit with transparent multi-burst chunking.
              </p>
            </div>

            <div className="pt-3 border-t border-zinc-800/80 space-y-1.5 text-[11px] font-mono">
              <div className="flex justify-between text-zinc-400">
                <span>DMR Max Packet:</span>
                <span className="text-zinc-200">280 Bytes (4B Hdr + 276B)</span>
              </div>
              <div className="flex justify-between text-zinc-400">
                <span>Physical RF:</span>
                <span className="text-amber-400 font-bold">Prohibited (Simulation)</span>
              </div>
            </div>
          </div>

          {/* STAR-V Tactical SDR Adapter (Clickable to open Lockout Dossier Modal) */}
          <div
            onClick={() => setIsStarVModalOpen(true)}
            className="bg-[#1C1318] border border-rose-500/60 hover:border-rose-400 shadow-[0_4px_24px_rgba(239,68,68,0.25)] p-4 rounded-xl space-y-3 flex flex-col justify-between cursor-pointer transition-all hover:scale-[1.01]"
          >
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-rose-400 uppercase font-semibold">
                  Tactical SDR
                </span>
                <span className="px-2 py-0.5 rounded bg-rose-950/90 text-rose-300 border border-rose-600 text-[10px] font-mono font-bold flex items-center space-x-1 shadow-[0_0_8px_rgba(244,63,94,0.4)]">
                  <Lock className="w-2.5 h-2.5" />
                  <span>PERMANENT SAFETY LOCKOUT ENFORCED</span>
                </span>
              </div>
              <h4 className="text-sm font-bold font-mono text-zinc-100 flex items-center space-x-2">
                <span>STAR-V Mk III Tactical SDR</span>
              </h4>
              <p className="text-xs text-zinc-300 font-sans leading-relaxed">
                Permanent software safety lockout enforced. Physical transmission strictly disabled until official vendor Interface Control Document (ICD) is verified.
              </p>
            </div>

            <div className="pt-3 border-t border-rose-900/60 space-y-2 text-[11px] font-mono">
              <div className="flex justify-between text-zinc-400">
                <span>Safety Lockout:</span>
                <span className="text-rose-400 font-bold">ACTIVE & ENFORCED</span>
              </div>
              <div className="flex justify-between text-zinc-400">
                <span>Vendor ICD:</span>
                <span className="text-rose-300">MISSING (0/4 Statutory Keys)</span>
              </div>

              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  setIsStarVModalOpen(true)
                }}
                className="w-full mt-2 py-1.5 px-3 rounded bg-rose-950/80 hover:bg-rose-900/90 border border-rose-600/80 text-rose-200 text-xs font-bold text-center transition-colors cursor-pointer"
              >
                [INSPECT SAFETY DOSSIER & RUN TESTS]
              </button>
            </div>
          </div>

          {/* LPI-CGAN Neural Transceiver */}
          <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-zinc-500 uppercase">Deep Learning SDR</span>
                <span className="px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800 text-[10px] font-mono font-bold">
                  VERIFIED ADAPTER
                </span>
              </div>
              <h4 className="text-sm font-bold font-mono text-zinc-100">
                LPI-CGAN Neural Transceiver
              </h4>
              <p className="text-xs text-zinc-400 font-sans leading-relaxed">
                Reed-Solomon RS(42,34) + CRC-8 framing modulated through neural generator with 9.03 dB spreading and keyed Zadoff-Chu synchronization.
              </p>
            </div>

            <div className="pt-3 border-t border-zinc-800/80 space-y-1.5 text-[11px] font-mono">
              <div className="flex justify-between text-zinc-400">
                <span>Spreading Factor:</span>
                <span className="text-emerald-400 font-bold">8x (9.03 dB)</span>
              </div>
              <div className="flex justify-between text-zinc-400">
                <span>Sample Rate:</span>
                <span className="text-zinc-200">245,760 Sa/s</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Section 3: Tactical Store-and-Forward Relay Gateways (D-07, D-08, T-04-04) */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 font-mono">
              Tactical Store-and-Forward Relay Gateways ({relays.length})
            </h3>
            <p className="text-[11px] text-zinc-400 font-sans">
              Autonomous intermediate store-and-forward telemetry, battery/storage failsafe cutoffs, and flight isolation
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {relays.map((relay) => {
            const battery = relay.battery_level_pct ?? relay.battery_percentage ?? 100
            const storage = relay.storage_usage_pct ?? relay.storage_used_pct ?? 0
            const queueDepth = relay.queue_depth ?? relay.queued_bundles_count ?? 0
            const forwardedCount = relay.forwarded_message_count ?? 0

            const isBatteryCritical = battery <= 5
            const isBatteryLow = battery <= 20
            const isStorageFull = storage >= 98
            const isStorageWarn = storage >= 80

            const isCutoff =
              isBatteryCritical ||
              isStorageFull ||
              relay.failsafe_cutoff_active ||
              relay.status === 'LOW_BATTERY' ||
              relay.status === 'STORAGE_FULL'

            const isAerial =
              relay.node_type === 'AERIAL_PAYLOAD_SIMULATED' ||
              relay.flight_failsafe_independent ||
              relay.node_id === 'relay-aerial-sim-01'

            const isBusy = updatingRelayId === relay.node_id

            return (
              <div
                key={relay.node_id}
                className={`bg-[#151D2A] border rounded-xl p-4 space-y-3.5 shadow-[0_4px_24px_rgba(6,182,212,0.15)] flex flex-col justify-between transition-all ${
                  isCutoff
                    ? 'border-rose-500/80 shadow-[0_0_20px_rgba(244,63,94,0.25)]'
                    : 'border-zinc-700/80'
                }`}
              >
                <div className="space-y-3">
                  {/* Top Bar: Node ID & Status */}
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono text-cyan-400 font-bold uppercase">
                      {relay.node_id}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${
                        isCutoff
                          ? 'bg-rose-950/80 border-rose-500/80 text-rose-300 animate-pulse'
                          : relay.status === 'ONLINE'
                          ? 'bg-emerald-950/60 border-emerald-700 text-emerald-400'
                          : 'bg-zinc-800 border-zinc-700 text-zinc-400'
                      }`}
                    >
                      {isCutoff ? 'CUTOFF ACTIVE' : relay.status}
                    </span>
                  </div>

                  {/* Title & Node Type */}
                  <div>
                    <h4 className="text-sm font-bold font-mono text-zinc-100 flex items-center space-x-1.5">
                      {isAerial ? <Plane className="w-4 h-4 text-emerald-400" /> : <Radio className="w-4 h-4 text-cyan-400" />}
                      <span>{relay.display_name}</span>
                    </h4>
                    <span className="text-[10px] font-mono text-zinc-500">{relay.node_type}</span>
                  </div>

                  {/* Autonomous Cutoff Badges */}
                  {isBatteryCritical && (
                    <div className="px-2 py-1 rounded bg-rose-950/80 border border-rose-500 text-rose-300 text-[10px] font-mono font-bold shadow-[0_0_10px_rgba(244,63,94,0.3)] animate-pulse">
                      AUTONOMOUS CUTOFF: BATTERY CRITICAL (&lt;= 5%)
                    </div>
                  )}
                  {isStorageFull && (
                    <div className="px-2 py-1 rounded bg-rose-950/80 border border-rose-500 text-rose-300 text-[10px] font-mono font-bold shadow-[0_0_10px_rgba(244,63,94,0.3)] animate-pulse">
                      AUTONOMOUS CUTOFF: STORAGE FULL (&gt;= 98%)
                    </div>
                  )}

                  {/* Aerial Relay Flight Isolation Badge */}
                  {isAerial && (
                    <div className="p-2 rounded bg-emerald-950/40 border border-emerald-500/60 space-y-1 shadow-[0_0_10px_rgba(16,185,129,0.15)]">
                      <div className="flex items-center space-x-1.5 text-emerald-400 font-bold text-[10px] font-mono">
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                        <span>[FLIGHT SAFETY ISOLATION: ACTIVE]</span>
                      </div>
                      <p className="text-[10px] text-zinc-400 font-sans leading-tight">
                        Communications payload strictly isolated from flight avionics/propulsion.
                      </p>
                    </div>
                  )}

                  {/* Telemetry Gauges */}
                  <div className="space-y-2 pt-2 border-t border-zinc-800 text-[11px] font-mono">
                    {/* Battery Gauge */}
                    <div className="space-y-1">
                      <div className="flex justify-between items-center text-zinc-400">
                        <span className="flex items-center space-x-1">
                          <Battery className="w-3 h-3 text-zinc-400" />
                          <span>Battery Level:</span>
                        </span>
                        <span
                          className={`font-bold ${
                            isBatteryCritical
                              ? 'text-red-400'
                              : isBatteryLow
                              ? 'text-amber-400'
                              : 'text-emerald-400'
                          }`}
                        >
                          {battery.toFixed(1)}%
                        </span>
                      </div>
                      <div className="w-full bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                        <div
                          className={`h-full transition-all duration-300 ${
                            isBatteryCritical
                              ? 'bg-red-500'
                              : isBatteryLow
                              ? 'bg-amber-500'
                              : 'bg-emerald-500'
                          }`}
                          style={{ width: `${Math.min(100, Math.max(0, battery))}%` }}
                        />
                      </div>
                    </div>

                    {/* Storage Gauge */}
                    <div className="space-y-1">
                      <div className="flex justify-between items-center text-zinc-400">
                        <span className="flex items-center space-x-1">
                          <HardDrive className="w-3 h-3 text-zinc-400" />
                          <span>Storage Utilized:</span>
                        </span>
                        <span
                          className={`font-bold ${
                            isStorageFull
                              ? 'text-red-400'
                              : isStorageWarn
                              ? 'text-amber-400'
                              : 'text-emerald-400'
                          }`}
                        >
                          {storage.toFixed(1)}%
                        </span>
                      </div>
                      <div className="w-full bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                        <div
                          className={`h-full transition-all duration-300 ${
                            isStorageFull
                              ? 'bg-red-500'
                              : isStorageWarn
                              ? 'bg-amber-500'
                              : 'bg-emerald-500'
                          }`}
                          style={{ width: `${Math.min(100, Math.max(0, storage))}%` }}
                        />
                      </div>
                    </div>

                    {/* Temperature, Queue & Forwarding */}
                    <div className="grid grid-cols-2 gap-2 pt-1 text-[10px] text-zinc-400">
                      <div className="flex items-center space-x-1">
                        <Thermometer className="w-3 h-3 text-zinc-500" />
                        <span>Temp:</span>
                        <span className="text-zinc-200 font-semibold">
                          {relay.temperature_celsius}°C
                        </span>
                      </div>
                      <div className="flex items-center space-x-1">
                        <Activity className="w-3 h-3 text-zinc-500" />
                        <span>Queue:</span>
                        <span className="text-zinc-200 font-semibold">{queueDepth}</span>
                      </div>
                    </div>

                    <div className="flex justify-between pt-1 text-[10px] text-zinc-400">
                      <span>Forwarding Status:</span>
                      <span className="text-cyan-300 font-bold">
                        FORWARDED: {forwardedCount} PACKETS
                      </span>
                    </div>
                  </div>
                </div>

                {/* Simulation Controls for Relay */}
                <div className="pt-3 border-t border-zinc-800/80 space-y-1.5">
                  <div className="text-[10px] text-zinc-500 font-mono uppercase font-semibold">
                    Telemetry Failsafe Simulation:
                  </div>
                  <div className="grid grid-cols-2 gap-1.5">
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => handleSimulateRelayLowBattery(relay.node_id)}
                      className="px-2 py-1 rounded bg-amber-950/60 hover:bg-amber-900/80 border border-amber-700/80 text-amber-300 text-[10px] font-mono font-bold transition-colors disabled:opacity-50 cursor-pointer text-center"
                    >
                      Sim Low Batt (4%)
                    </button>
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => handleSimulateRelayStorageFull(relay.node_id)}
                      className="px-2 py-1 rounded bg-red-950/60 hover:bg-red-900/80 border border-red-700/80 text-red-300 text-[10px] font-mono font-bold transition-colors disabled:opacity-50 cursor-pointer text-center"
                    >
                      Sim Storage (99%)
                    </button>
                  </div>
                  <button
                    type="button"
                    disabled={isBusy}
                    onClick={() => handleResetRelay(relay.node_id)}
                    className="w-full py-1 rounded bg-zinc-800 hover:bg-zinc-700 border border-zinc-600 text-zinc-200 text-[10px] font-mono transition-colors disabled:opacity-50 cursor-pointer flex items-center justify-center space-x-1"
                  >
                    <RotateCcw className={`w-2.5 h-2.5 ${isBusy ? 'animate-spin' : ''}`} />
                    <span>Reset to Nominal</span>
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* STAR-V Software Safety Lockout Dossier Modal */}
      <StarVLockoutDossierModal
        isOpen={isStarVModalOpen}
        onClose={() => setIsStarVModalOpen(false)}
      />
    </div>
  )
}
