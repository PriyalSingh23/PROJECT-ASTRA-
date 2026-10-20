import React, { useState, useEffect, useCallback } from 'react'
import {
  Wifi,
  WifiOff,
  Server,
  Cpu,
  Sliders,
  RotateCcw,
  Radio,
  Zap,
  Battery,
  HardDrive,
  Thermometer,
  ShieldAlert,
  Flame,
  Volume2,
  VolumeX,
} from 'lucide-react'
import { QueueStats, RelayNode } from '../types'
import { api } from '../services/api'
import { audioService } from '../services/audioService'

interface ConnectivityViewProps {
  queueStats: QueueStats | null
  isBackendHealthy: boolean
  onRefresh: () => void
}

export const ConnectivityView: React.FC<ConnectivityViewProps> = ({
  queueStats,
  isBackendHealthy,
  onRefresh,
}) => {
  // Independent Connectivity States
  const [isInternetOnline, setIsInternetOnline] = useState<boolean>(
    typeof navigator !== 'undefined' ? navigator.onLine : true
  )
  const [relays, setRelays] = useState<RelayNode[]>([])
  const [isMuted, setIsMuted] = useState<boolean>(audioService.getMuted())

  // Simulation Controls
  const [simConfig, setSimConfig] = useState({
    is_online: queueStats?.transport?.is_online ?? true,
    latency_ms: queueStats?.transport?.latency_ms ?? 0,
    drop_message_prob: queueStats?.transport?.drop_rate ?? 0,
    drop_ack_prob: queueStats?.transport?.ack_drop_rate ?? 0,
  })
  const [activePreset, setActivePreset] = useState<string>('NOMINAL')
  const [armedFaults, setArmedFaults] = useState<{
    drop_message: boolean
    drop_ack: boolean
    corrupt_hmac: boolean
  }>({
    drop_message: false,
    drop_ack: false,
    corrupt_hmac: false,
  })

  // Backoff Retry Profile
  const [retryProfile, setRetryProfile] = useState<{
    active_profile: 'FAST' | 'TACTICAL'
    base_delay: number
    max_delay: number
    jitter: number
  }>({
    active_profile: 'TACTICAL',
    base_delay: 2.0,
    max_delay: 60.0,
    jitter: 0.5,
  })

  const [isUpdatingSim, setIsUpdatingSim] = useState(false)
  const [simNotice, setSimNotice] = useState<string | null>(null)

  // Track browser internet status
  useEffect(() => {
    const handleOnline = () => setIsInternetOnline(true)
    const handleOffline = () => setIsInternetOnline(false)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  // Sync simulation config and profiles from backend
  const fetchSimState = useCallback(async () => {
    try {
      const [transportStatus, profileData] = await Promise.all([
        api.getSimTransport(),
        api.getRetryProfile().catch(() => null),
      ])
      if (transportStatus) {
        setSimConfig({
          is_online: transportStatus.is_online ?? true,
          latency_ms: transportStatus.latency_ms ?? 0,
          drop_message_prob: transportStatus.drop_message_prob ?? 0,
          drop_ack_prob: transportStatus.drop_ack_prob ?? 0,
        })
        if (transportStatus.active_preset) {
          setActivePreset(transportStatus.active_preset)
        }
        if (transportStatus.armed_faults) {
          setArmedFaults(transportStatus.armed_faults)
        }
      }
      if (profileData) {
        setRetryProfile(profileData)
      }
    } catch (err) {
      console.warn('Could not refresh transport / profile status:', err)
    }
  }, [])

  useEffect(() => {
    fetchSimState()
  }, [fetchSimState])

  // Sync simulation config from incoming queueStats prop
  useEffect(() => {
    const transport = queueStats?.transport
    if (transport) {
      setSimConfig((prev) => ({
        ...prev,
        is_online: transport.is_online,
        latency_ms: transport.latency_ms,
        drop_message_prob: transport.drop_rate,
        drop_ack_prob: transport.ack_drop_rate,
      }))
    }
  }, [queueStats])

  // Fetch ground relay nodes
  useEffect(() => {
    api
      .getRelays()
      .then((data) => setRelays(data))
      .catch((err) => console.warn('Could not fetch relays:', err))
  }, [])

  const handleUpdateSim = async (partial: Partial<typeof simConfig>) => {
    const nextConfig = { ...simConfig, ...partial }
    setSimConfig(nextConfig)
    setIsUpdatingSim(true)
    setSimNotice(null)
    try {
      await api.updateSimTransport(nextConfig)
      if (partial.is_online === false) {
        audioService.playSquelch()
      } else if (partial.is_online === true) {
        audioService.playRestoreChime()
      }
      onRefresh()
    } catch (err: any) {
      setSimNotice(`Error updating simulation: ${err.message}`)
    } finally {
      setIsUpdatingSim(false)
    }
  }

  const handleSelectPreset = async (presetName: string) => {
    setIsUpdatingSim(true)
    setSimNotice(null)
    try {
      const res = await api.updateSimTransport({ preset: presetName })
      setActivePreset(presetName)
      setSimConfig({
        is_online: res.is_online,
        latency_ms: res.latency_ms,
        drop_message_prob: res.drop_message_prob,
        drop_ack_prob: res.drop_ack_prob,
      })
      if (presetName === 'NOMINAL') {
        audioService.playRestoreChime()
      } else {
        audioService.playSquelch()
      }
      setSimNotice(`Tactical Preset Activated: ${presetName}`)
      onRefresh()
    } catch (err: any) {
      setSimNotice(`Preset error: ${err.message}`)
    } finally {
      setIsUpdatingSim(false)
    }
  }

  const handleRestoreCleanLink = async () => {
    setIsUpdatingSim(true)
    try {
      await api.updateSimTransport({ reset: true, preset: 'NOMINAL' })
      setActivePreset('NOMINAL')
      setArmedFaults({ drop_message: false, drop_ack: false, corrupt_hmac: false })
      setSimConfig({ is_online: true, latency_ms: 0, drop_message_prob: 0, drop_ack_prob: 0 })
      audioService.playRestoreChime()
      onRefresh()
      setSimNotice('Clean link restored (0ms latency, 0% drops, all armed faults cleared).')
    } catch (err: any) {
      setSimNotice(`Restore error: ${err.message}`)
    } finally {
      setIsUpdatingSim(false)
    }
  }

  const handleArmFault = async (action: string) => {
    try {
      const res = await api.armFault(action)
      if (res.armed_faults) {
        setArmedFaults(res.armed_faults)
      }
      audioService.playSquelch()
      setSimNotice(`Single-shot fault armed: ${action}. Will auto-disarm immediately after next message.`)
      onRefresh()
    } catch (err: any) {
      setSimNotice(`Arm fault failed: ${err.message}`)
    }
  }

  const handleDisarmAll = async () => {
    try {
      const res = await api.disarmAllFaults()
      if (res.armed_faults) {
        setArmedFaults(res.armed_faults)
      }
      setSimNotice('All armed single-shot faults disarmed.')
      onRefresh()
    } catch (err: any) {
      setSimNotice(`Disarm failed: ${err.message}`)
    }
  }

  const handleSimulateWorkerCrash = async () => {
    try {
      const res = await api.simulateWorkerCrash()
      setSimNotice(`Worker Crash Simulated: Message ${res.message_id.slice(0, 8)}... leased with expired deadline.`)
      onRefresh()
    } catch (err: any) {
      setSimNotice(`Crash simulation failed: ${err.message}`)
    }
  }

  const handleTriggerReclaim = async () => {
    try {
      const res = await api.triggerLeaseReclaim()
      setSimNotice(`Lease Reclamation Complete: ${res.reclaimed_count} orphaned message lease(s) recovered to QUEUED.`)
      onRefresh()
    } catch (err: any) {
      setSimNotice(`Reclaim failed: ${err.message}`)
    }
  }

  const handleToggleRetryProfile = async (profile: 'FAST' | 'TACTICAL') => {
    try {
      const res = await api.setRetryProfile(profile)
      setRetryProfile(res)
      setSimNotice(`Backoff Profile Configured: ${profile} (base: ${res.base_delay}s, max: ${res.max_delay}s)`)
    } catch (err: any) {
      setSimNotice(`Profile switch error: ${err.message}`)
    }
  }

  const handleToggleAudio = () => {
    const nextMuted = audioService.toggleMute()
    setIsMuted(nextMuted)
  }

  const hasArmedFaults =
    armedFaults.drop_message || armedFaults.drop_ack || armedFaults.corrupt_hmac

  return (
    <div className="max-w-7xl w-full mx-auto space-y-6">
      <style>{`
        @keyframes tacticalRadarSweep {
          0% { transform: translateY(-100%); opacity: 0; }
          25% { opacity: 0.9; }
          75% { opacity: 0.9; }
          100% { transform: translateY(450%); opacity: 0; }
        }
        .animate-radar-sweep {
          animation: tacticalRadarSweep 2.8s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }
      `}</style>

      {/* Global Notice Banner */}
      {simNotice && (
        <div className="bg-amber-950/40 border border-amber-500/50 p-3 rounded-xl flex items-center justify-between text-xs font-mono text-amber-200">
          <span>{simNotice}</span>
          <button
            onClick={() => setSimNotice(null)}
            className="text-amber-400 hover:text-white px-2 py-0.5 rounded text-[10px]"
          >
            DISMISS
          </button>
        </div>
      )}

      {/* Overview Cards: Independent Connectivity Vectors */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-zinc-400">
            Independent Network Vectors
          </h3>
          <div className="flex items-center space-x-2">
            <button
              onClick={handleToggleAudio}
              className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-[11px] font-mono text-zinc-400 hover:text-zinc-200"
              title="Toggle Web Audio sound synthesis"
            >
              {isMuted ? <VolumeX className="w-3.5 h-3.5 text-zinc-500" /> : <Volume2 className="w-3.5 h-3.5 text-emerald-400" />}
              <span>{isMuted ? 'AUDIO: MUTED' : 'AUDIO: ON'}</span>
            </button>
            <button
              onClick={handleRestoreCleanLink}
              disabled={isUpdatingSim}
              className="flex items-center space-x-1.5 px-3 py-1 rounded-md bg-emerald-950/40 hover:bg-emerald-900/50 text-emerald-300 border border-emerald-700/60 text-xs font-mono font-bold shadow-[0_0_15px_rgba(16,185,129,0.2)] transition-all"
            >
              <RotateCcw className="w-3.5 h-3.5 text-emerald-400" />
              <span>Restore Clean Link</span>
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* 1. Public Internet Connectivity */}
          <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl flex items-start space-x-3">
            <div
              className={`p-2 rounded-lg ${
                isInternetOnline
                  ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-800/60'
                  : 'bg-rose-950/40 text-rose-400 border border-rose-800/60'
              }`}
            >
              {isInternetOnline ? <Wifi className="w-5 h-5" /> : <WifiOff className="w-5 h-5" />}
            </div>
            <div>
              <span className="text-[10px] font-mono uppercase text-zinc-400">Public Internet</span>
              <p className="text-sm font-bold font-mono text-zinc-100 mt-0.5">
                {isInternetOnline ? 'CONNECTED' : 'DISCONNECTED'}
              </p>
              <p className="text-[11px] text-zinc-500 font-sans mt-0.5">
                {isInternetOnline ? 'External gateway reachable' : 'Operating in complete air-gap'}
              </p>
            </div>
          </div>

          {/* 2. Local Backend REST API Health */}
          <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl flex items-start space-x-3">
            <div
              className={`p-2 rounded-lg ${
                isBackendHealthy
                  ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-800/60'
                  : 'bg-rose-950/40 text-rose-400 border border-rose-800/60'
              }`}
            >
              <Server className="w-5 h-5" />
            </div>
            <div>
              <span className="text-[10px] font-mono uppercase text-zinc-400">Local Backend API</span>
              <p className="text-sm font-bold font-mono text-zinc-100 mt-0.5">
                {isBackendHealthy ? 'HEALTHY (Port 5050)' : 'UNREACHABLE'}
              </p>
              <p className="text-[11px] text-zinc-500 font-sans mt-0.5">
                SQLite WAL mode with atomic transactions
              </p>
            </div>
          </div>

          {/* 3. Queue Worker Daemon */}
          <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl flex items-start space-x-3">
            <div className="p-2 rounded-lg bg-cyan-950/40 text-cyan-400 border border-cyan-800/60">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <span className="text-[10px] font-mono uppercase text-zinc-400">Delivery Worker</span>
              <p className="text-sm font-bold font-mono text-zinc-100 mt-0.5">
                {queueStats?.active_leases ? `${queueStats.active_leases} LEASES ACTIVE` : 'IDLE / POLLING'}
              </p>
              <p className="text-[11px] text-zinc-500 font-sans mt-0.5">
                Atomic lease recovery ceiling: 30s timeout
              </p>
            </div>
          </div>

          {/* 4. Virtual RF Channel Link with Radar Sweep Effect */}
          <div className="relative overflow-hidden bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl flex items-start space-x-3">
            {simConfig.is_online && (
              <div className="absolute inset-0 pointer-events-none overflow-hidden rounded-xl">
                <div className="w-full h-1 bg-gradient-to-r from-transparent via-emerald-400/70 to-transparent blur-[1px] animate-radar-sweep" />
              </div>
            )}
            <div
              className={`p-2 rounded-lg relative z-10 ${
                simConfig.is_online
                  ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-800/60'
                  : 'bg-amber-950/40 text-amber-400 border border-amber-800/60'
              }`}
            >
              <Radio className="w-5 h-5" />
            </div>
            <div className="relative z-10">
              <span className="text-[10px] font-mono uppercase text-zinc-400">Virtual RF Transport</span>
              <p className="text-sm font-bold font-mono text-zinc-100 mt-0.5">
                {simConfig.is_online ? 'ONLINE' : 'SEVERED / OUTAGE'}
              </p>
              <p className="text-[11px] text-zinc-500 font-sans mt-0.5">
                {simConfig.latency_ms}ms latency &bull; {Math.round(simConfig.drop_message_prob * 100)}% drops
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Tactical Quick-Select Presets (D-01) */}
      <div className="bg-zinc-900/60 border border-zinc-800 p-5 rounded-xl space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Zap className="w-4 h-4 text-emerald-400" />
            <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-zinc-300">
              Tactical Quick-Select Presets
            </h3>
          </div>
          <span className="text-[10px] font-mono text-zinc-500">
            ACTIVE PRESET: <span className="text-emerald-400 font-bold">{activePreset}</span>
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Preset 1: Nominal */}
          <button
            onClick={() => handleSelectPreset('NOMINAL')}
            className={`p-3 rounded-lg border text-left transition-all ${
              activePreset === 'NOMINAL'
                ? 'bg-emerald-950/40 border-emerald-500 text-emerald-100 shadow-[0_0_16px_rgba(16,185,129,0.25)]'
                : 'bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-bold">Nominal Clear Link</span>
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
            </div>
            <p className="text-[10px] font-mono text-zinc-500 mt-1">0ms latency &bull; 0% drops</p>
            <p className="text-[10px] text-zinc-400 mt-0.5">Standard high-throughput link</p>
          </button>

          {/* Preset 2: Urban Jamming */}
          <button
            onClick={() => handleSelectPreset('URBAN_JAMMING')}
            className={`p-3 rounded-lg border text-left transition-all ${
              activePreset === 'URBAN_JAMMING'
                ? 'bg-amber-950/40 border-amber-500 text-amber-100 shadow-[0_0_16px_rgba(245,158,11,0.25)]'
                : 'bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-bold">Urban EW Jamming</span>
              <span className="w-2 h-2 rounded-full bg-amber-500" />
            </div>
            <p className="text-[10px] font-mono text-zinc-500 mt-1">50ms &bull; 30% drop / 10% ACK</p>
            <p className="text-[10px] text-zinc-400 mt-0.5">Hostile dense spectral interference</p>
          </button>

          {/* Preset 3: Air Gap */}
          <button
            onClick={() => handleSelectPreset('AIR_GAP')}
            className={`p-3 rounded-lg border text-left transition-all ${
              activePreset === 'AIR_GAP'
                ? 'bg-rose-950/40 border-rose-500 text-rose-100 shadow-[0_0_16px_rgba(239,68,68,0.25)]'
                : 'bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-bold">Severed Air-Gap Outage</span>
              <span className="w-2 h-2 rounded-full bg-rose-500" />
            </div>
            <p className="text-[10px] font-mono text-zinc-500 mt-1">OFFLINE &bull; 100% loss</p>
            <p className="text-[10px] text-zinc-400 mt-0.5">Physical disconnection test</p>
          </button>

          {/* Preset 4: Satellite */}
          <button
            onClick={() => handleSelectPreset('SATELLITE')}
            className={`p-3 rounded-lg border text-left transition-all ${
              activePreset === 'SATELLITE'
                ? 'bg-cyan-950/40 border-cyan-500 text-cyan-100 shadow-[0_0_16px_rgba(6,182,212,0.25)]'
                : 'bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-bold">GEO Satellite Link</span>
              <span className="w-2 h-2 rounded-full bg-cyan-500" />
            </div>
            <p className="text-[10px] font-mono text-zinc-500 mt-1">800ms latency &bull; 5% drops</p>
            <p className="text-[10px] text-zinc-400 mt-0.5">High round-trip delay channel</p>
          </button>
        </div>
      </div>

      {/* Single-Shot Armed Faults & Auto-Disarm (D-03) */}
      <div className="bg-zinc-900/60 border border-zinc-800 p-5 rounded-xl space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <ShieldAlert className="w-4 h-4 text-amber-400" />
            <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-zinc-300">
              Single-Shot Armed Faults (Auto-Disarming)
            </h3>
          </div>
          {hasArmedFaults && (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-950/60 border border-amber-600/70 text-amber-300 animate-pulse">
              1 OR MORE FAULTS ARMED
            </span>
          )}
        </div>

        <p className="text-xs text-zinc-400 font-sans">
          Arm a deterministic fault that fires exactly once upon the next message transmission, then immediately auto-disarms to prevent channel contamination.
        </p>

        {/* Active Armed Status Chips */}
        {hasArmedFaults && (
          <div className="flex flex-wrap items-center gap-2 pt-1 pb-1">
            {armedFaults.drop_message && (
              <span className="text-[11px] font-mono font-bold px-2.5 py-1 rounded-md bg-amber-950/80 border border-amber-500 text-amber-200 shadow-[0_0_10px_rgba(245,158,11,0.3)] animate-pulse">
                ARMED: DROP NEXT MESSAGE
              </span>
            )}
            {armedFaults.drop_ack && (
              <span className="text-[11px] font-mono font-bold px-2.5 py-1 rounded-md bg-amber-950/80 border border-amber-500 text-amber-200 shadow-[0_0_10px_rgba(245,158,11,0.3)] animate-pulse">
                ARMED: DROP NEXT ACK
              </span>
            )}
            {armedFaults.corrupt_hmac && (
              <span className="text-[11px] font-mono font-bold px-2.5 py-1 rounded-md bg-rose-950/80 border border-rose-500 text-rose-200 shadow-[0_0_10px_rgba(239,68,68,0.3)] animate-pulse">
                ARMED: CORRUPT HMAC
              </span>
            )}
          </div>
        )}

        {/* Arming Trigger Buttons */}
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-zinc-800">
          <button
            onClick={() => handleArmFault('arm_drop_message')}
            className={`px-3 py-1.5 rounded-md border text-xs font-mono font-bold transition-all ${
              armedFaults.drop_message
                ? 'bg-amber-600 text-white border-amber-500'
                : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border-zinc-700'
            }`}
          >
            Arm Drop Next Message
          </button>
          <button
            onClick={() => handleArmFault('arm_drop_ack')}
            className={`px-3 py-1.5 rounded-md border text-xs font-mono font-bold transition-all ${
              armedFaults.drop_ack
                ? 'bg-amber-600 text-white border-amber-500'
                : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border-zinc-700'
            }`}
          >
            Arm Drop Next ACK
          </button>
          <button
            onClick={() => handleArmFault('arm_corrupt_hmac')}
            className={`px-3 py-1.5 rounded-md border text-xs font-mono font-bold transition-all ${
              armedFaults.corrupt_hmac
                ? 'bg-rose-600 text-white border-rose-500'
                : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border-zinc-700'
            }`}
          >
            Arm Corrupt Next HMAC
          </button>
          <button
            onClick={handleDisarmAll}
            className="px-3 py-1.5 rounded-md bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 border border-zinc-800 text-xs font-mono transition-colors ml-auto"
          >
            Disarm All Faults
          </button>
        </div>
      </div>

      {/* Worker Crash Recovery & Lease Reclamation (D-15) */}
      <div className="bg-zinc-900/60 border border-zinc-800 p-5 rounded-xl space-y-3">
        <div className="flex items-center space-x-2">
          <Flame className="w-4 h-4 text-rose-400" />
          <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-zinc-300">
            Worker Crash Recovery & Stale Lease Reclamation
          </h3>
        </div>

        <p className="text-xs text-zinc-400 font-sans">
          Simulate worker process SIGKILL termination mid-flight and test atomic orphan reclamation without message loss.
        </p>

        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-zinc-800">
          <button
            onClick={handleSimulateWorkerCrash}
            className="px-3.5 py-1.5 rounded-md bg-rose-950/50 hover:bg-rose-900/60 text-rose-200 border border-rose-800/70 text-xs font-mono font-bold transition-colors flex items-center space-x-2"
          >
            <Flame className="w-3.5 h-3.5 text-rose-400" />
            <span>Simulate Worker Crash (Abort Lease)</span>
          </button>

          <button
            onClick={handleTriggerReclaim}
            className="px-3.5 py-1.5 rounded-md bg-cyan-950/50 hover:bg-cyan-900/60 text-cyan-200 border border-cyan-800/70 text-xs font-mono font-bold transition-colors flex items-center space-x-2"
          >
            <Cpu className="w-3.5 h-3.5 text-cyan-400" />
            <span>Trigger Immediate Lease Reclamation</span>
          </button>
        </div>
      </div>

      {/* Dual-Profile Backoff Retry Tuner (D-20) */}
      <div className="bg-zinc-900/60 border border-zinc-800 p-5 rounded-xl space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Sliders className="w-4 h-4 text-cyan-400" />
            <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-zinc-300">
              Exponential Backoff Retry Profile
            </h3>
          </div>
          <span className="text-[10px] font-mono text-zinc-400">
            ACTIVE PROFILE:{' '}
            <span className="text-cyan-400 font-bold">{retryProfile.active_profile}</span>
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
          {/* Fast Retries Toggle */}
          <button
            onClick={() => handleToggleRetryProfile('FAST')}
            className={`p-3 rounded-lg border text-left transition-all ${
              retryProfile.active_profile === 'FAST'
                ? 'bg-cyan-950/40 border-cyan-500 text-cyan-100 shadow-[0_0_15px_rgba(6,182,212,0.25)]'
                : 'bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200'
            }`}
          >
            <div className="flex justify-between items-center">
              <span className="text-xs font-mono font-bold">Demo Fast Retries</span>
              <span className="text-[10px] font-mono bg-cyan-900/60 text-cyan-300 px-1.5 py-0.5 rounded">0.5s / 5s</span>
            </div>
            <p className="text-[10px] font-mono text-zinc-500 mt-1">
              Base: 0.5s &bull; Ceiling: 5.0s &bull; Jitter: ±0.1s
            </p>
            <p className="text-[11px] text-zinc-400 mt-0.5 font-sans">
              Optimized for live interactive test evaluation and immediate feedback
            </p>
          </button>

          {/* Tactical Field Toggle */}
          <button
            onClick={() => handleToggleRetryProfile('TACTICAL')}
            className={`p-3 rounded-lg border text-left transition-all ${
              retryProfile.active_profile === 'TACTICAL'
                ? 'bg-emerald-950/40 border-emerald-500 text-emerald-100 shadow-[0_0_15px_rgba(16,185,129,0.25)]'
                : 'bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200'
            }`}
          >
            <div className="flex justify-between items-center">
              <span className="text-xs font-mono font-bold">Tactical Field Schedule</span>
              <span className="text-[10px] font-mono bg-emerald-900/60 text-emerald-300 px-1.5 py-0.5 rounded">2s / 60s</span>
            </div>
            <p className="text-[10px] font-mono text-zinc-500 mt-1">
              Base: 2.0s &bull; Ceiling: 60.0s &bull; Jitter: ±0.5s
            </p>
            <p className="text-[11px] text-zinc-400 mt-0.5 font-sans">
              Operational profile: 2s, 4s, 8s, 16s, 32s with channel quiescence
            </p>
          </button>
        </div>
      </div>

      {/* Manual Fine-Tuning Sliders */}
      <div className="bg-zinc-900/60 border border-zinc-800 p-5 rounded-xl space-y-4">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div>
            <h3 className="text-sm font-bold font-mono text-zinc-100 flex items-center space-x-2">
              <Sliders className="w-4 h-4 text-emerald-400" />
              <span>Manual Channel Fine-Tuning</span>
            </h3>
            <p className="text-xs text-zinc-400 font-sans mt-0.5">
              Granularly configure continuous channel impairment parameters
            </p>
          </div>
        </div>

        {/* Controls Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Link Status Toggle */}
          <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 space-y-2">
            <span className="text-[10px] font-mono uppercase text-zinc-400">Transport Link Switch</span>
            <div className="flex items-center space-x-2">
              <button
                onClick={() => handleUpdateSim({ is_online: true })}
                className={`flex-1 py-1.5 rounded text-xs font-mono font-bold transition-colors ${
                  simConfig.is_online
                    ? 'bg-emerald-600 text-white shadow'
                    : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
                }`}
              >
                ONLINE
              </button>
              <button
                onClick={() => handleUpdateSim({ is_online: false })}
                className={`flex-1 py-1.5 rounded text-xs font-mono font-bold transition-colors ${
                  !simConfig.is_online
                    ? 'bg-amber-600 text-white shadow'
                    : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
                }`}
              >
                SEVERED
              </button>
            </div>
            <p className="text-[10px] text-zinc-500 font-sans">
              Severing link forces local IndexedDB caching and backend queuing.
            </p>
          </div>

          {/* Latency Slider */}
          <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 space-y-2">
            <div className="flex justify-between items-center text-xs font-mono">
              <span className="text-zinc-400">Simulated Latency:</span>
              <span className="text-emerald-400 font-bold">{simConfig.latency_ms} ms</span>
            </div>
            <input
              type="range"
              min={0}
              max={1500}
              step={50}
              value={simConfig.latency_ms}
              onChange={(e) => handleUpdateSim({ latency_ms: Number(e.target.value) })}
              className="w-full accent-emerald-500 cursor-pointer"
            />
            <p className="text-[10px] text-zinc-500 font-sans">Artificial per-hop delay.</p>
          </div>

          {/* Message Packet Drop Rate */}
          <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 space-y-2">
            <div className="flex justify-between items-center text-xs font-mono">
              <span className="text-zinc-400">Message Drop Rate:</span>
              <span className="text-amber-400 font-bold">
                {Math.round(simConfig.drop_message_prob * 100)}%
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={simConfig.drop_message_prob}
              onChange={(e) => handleUpdateSim({ drop_message_prob: Number(e.target.value) })}
              className="w-full accent-amber-500 cursor-pointer"
            />
            <p className="text-[10px] text-zinc-500 font-sans">Simulates lossy RF link.</p>
          </div>

          {/* ACK Drop Rate */}
          <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 space-y-2">
            <div className="flex justify-between items-center text-xs font-mono">
              <span className="text-zinc-400">ACK Drop Rate:</span>
              <span className="text-rose-400 font-bold">
                {Math.round(simConfig.drop_ack_prob * 100)}%
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={simConfig.drop_ack_prob}
              onChange={(e) => handleUpdateSim({ drop_ack_prob: Number(e.target.value) })}
              className="w-full accent-rose-500 cursor-pointer"
            />
            <p className="text-[10px] text-zinc-500 font-sans">Tests duplicate ACK handling.</p>
          </div>
        </div>
      </div>

      {/* Ground & Mobile Relays Monitoring */}
      <div className="space-y-3">
        <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-zinc-400">
          Decoupled Ground & Mobile Relay Nodes
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {relays.map((relay) => (
            <div
              key={relay.node_id}
              className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-3"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold font-mono text-zinc-100">{relay.display_name}</h4>
                  <span className="text-[10px] font-mono text-zinc-400">{relay.node_id}</span>
                </div>
                <span
                  className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded border ${
                    relay.status === 'ONLINE'
                      ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800'
                      : 'bg-amber-950/40 text-amber-400 border-amber-800'
                  }`}
                >
                  {relay.status}
                </span>
              </div>

              {/* Telemetry Grid */}
              <div className="grid grid-cols-3 gap-2 text-xs font-mono bg-zinc-950 p-2.5 rounded-lg border border-zinc-850">
                <div className="flex items-center space-x-1.5">
                  <Battery className="w-3.5 h-3.5 text-emerald-400" />
                  <div>
                    <span className="text-[9px] text-zinc-500 block">Battery</span>
                    <span className="text-zinc-200 font-bold">{relay.battery_level_pct}%</span>
                  </div>
                </div>

                <div className="flex items-center space-x-1.5">
                  <Thermometer className="w-3.5 h-3.5 text-sky-400" />
                  <div>
                    <span className="text-[9px] text-zinc-500 block">Temp</span>
                    <span className="text-zinc-200 font-bold">{relay.temperature_celsius}°C</span>
                  </div>
                </div>

                <div className="flex items-center space-x-1.5">
                  <HardDrive className="w-3.5 h-3.5 text-amber-400" />
                  <div>
                    <span className="text-[9px] text-zinc-500 block">Storage</span>
                    <span className="text-zinc-200 font-bold">{relay.storage_usage_pct}%</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between text-[11px] text-zinc-400 font-sans pt-1">
                <span>Queued Bundles: {relay.queued_bundles_count}</span>
                <span className="text-emerald-400 font-mono text-[10px]">
                  Failsafe: {relay.is_independent_payload ? 'Independent Payload' : 'Direct'}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
