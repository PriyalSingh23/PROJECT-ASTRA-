import React from 'react'
import {
  Radio,
  Activity,
  Wifi,
  WifiOff,
  User as UserIcon,
  LogOut,
  LogIn,
  Compass,
  BookOpen,
  Waves,
  Package,
  Volume2,
  VolumeX,
  Lock,
} from 'lucide-react'
import { QueueStats, User } from '../types'
import { audioService } from '../services/audioService'
import { api, alphaApi, bravoApi } from '../services/api'

export type WorkstationTab =
  | 'overview'
  | 'topology'
  | 'transmitter'
  | 'receiver'
  | 'analyser'
  | 'channel'
  | 'models'
  | 'experiments'
  | 'pipeline'
  | 'messages'
  | 'connectivity'
  | 'devices'
  | 'diagnostics'
  | 'research'
  | 'waveform'
  | 'security'

interface HeaderProps {
  activeTab: WorkstationTab
  setActiveTab: (tab: WorkstationTab) => void
  isBackendHealthy: boolean
  alphaHealth?: { healthy: boolean; port: number; dbPath: string } | null
  bravoHealth?: { healthy: boolean; port: number; dbPath: string } | null
  queueStats: QueueStats | null
  currentUser: User | null
  localOutboxCount?: number
  onFlushOutbox?: () => void
  onOpenAuth: () => void
  onLogout: () => void
  onOpenDemo: () => void
  onOpenTour?: (mode: 'beginner' | 'experiment') => void
  onOpenHelp?: () => void
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  isBackendHealthy,
  alphaHealth,
  bravoHealth,
  queueStats,
  currentUser,
  localOutboxCount,
  onFlushOutbox,
  onOpenAuth,
  onLogout,
  onOpenDemo,
  onOpenTour,
  onOpenHelp,
}) => {
  const [isMuted, setIsMuted] = React.useState<boolean>(audioService.getMuted())
  const [internalAlpha, setInternalAlpha] = React.useState<{ healthy: boolean; port: number; dbPath: string }>({
    healthy: false,
    port: 5051,
    dbPath: 'alpha.db',
  })
  const [internalBravo, setInternalBravo] = React.useState<{ healthy: boolean; port: number; dbPath: string }>({
    healthy: false,
    port: 5052,
    dbPath: 'bravo.db',
  })
  const [comsecStatus, setComsecStatus] = React.useState<'READY' | 'ZEROIZED' | 'UNLOADED'>('READY')

  React.useEffect(() => {
    let mounted = true
    const checkDaemons = async () => {
      try {
        const aMeta = await alphaApi.getHealth()
        if (mounted) {
          setInternalAlpha({
            healthy: aMeta.status === 'HEALTHY',
            port: aMeta.port || 5051,
            dbPath: aMeta.db_path || 'alpha.db',
          })
        }
      } catch {
        if (mounted) {
          setInternalAlpha(prev => ({ ...prev, healthy: false }))
        }
      }

      try {
        const bMeta = await bravoApi.getHealth()
        if (mounted) {
          setInternalBravo({
            healthy: bMeta.status === 'HEALTHY',
            port: bMeta.port || 5052,
            dbPath: bMeta.db_path || 'bravo.db',
          })
        }
      } catch {
        if (mounted) {
          setInternalBravo(prev => ({ ...prev, healthy: false }))
        }
      }

      try {
        const keys = await api.getPublicKeys()
        if (mounted) {
          if (!keys || keys.is_zeroized || !keys.public_key_pqc) {
            if (keys && keys.is_zeroized) {
              setComsecStatus('ZEROIZED')
            } else {
              setComsecStatus('UNLOADED')
            }
          } else {
            setComsecStatus('READY')
          }
        }
      } catch {
        if (mounted) {
          setComsecStatus('UNLOADED')
        }
      }
    }

    checkDaemons()
    const timer = setInterval(checkDaemons, 3000)
    return () => {
      mounted = false
      clearInterval(timer)
    }
  }, [])

  const effAlpha = alphaHealth ?? internalAlpha
  const effBravo = bravoHealth ?? internalBravo
  return (
    <header className="border-b border-zinc-800 bg-zinc-950 text-zinc-100 sticky top-0 z-40 select-none">
      <div className="max-w-7xl mx-auto px-4 py-2 flex flex-col md:flex-row md:items-center md:justify-between gap-2.5">
        {/* Brand & Subtitle */}
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
            <Radio className="w-4 h-4 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold tracking-wider text-sm text-zinc-100 font-mono">ASTRA</span>
              <span className="text-[9px] uppercase font-mono px-1.5 py-0.2 rounded bg-emerald-950/80 border border-emerald-600/40 text-emerald-300 font-bold">
                WORKSTATION v4.2
              </span>
              <span className="text-[9px] uppercase font-mono px-1.5 py-0.2 rounded bg-zinc-800 border border-zinc-700 text-zinc-300">
                2.484 GHz
              </span>
            </div>
            <p className="text-[11px] text-zinc-400 font-sans">
              Adaptive Secure Transmission &amp; Research Architecture
            </p>
          </div>
        </div>

        {/* Demo Mode & Right Controls */}
        <div className="flex items-center space-x-2 text-xs">
          {/* Guide Me Button */}
          {onOpenTour && (
            <button
              onClick={() => onOpenTour('experiment')}
              className="flex items-center space-x-1 px-2.5 py-1 bg-gradient-to-r from-cyan-600/25 to-blue-600/25 hover:from-cyan-600/35 hover:to-blue-600/35 text-cyan-300 border border-cyan-500/40 rounded-md font-mono text-[11px] font-bold transition-all shadow-sm"
              title="Launch guided interactive communication experiment"
            >
              <Compass className="w-3.5 h-3.5 text-cyan-400" />
              <span>Guide Me</span>
            </button>
          )}

          {/* Help Centre Button */}
          {onOpenHelp && (
            <button
              onClick={onOpenHelp}
              className="flex items-center space-x-1 px-2.5 py-1 bg-zinc-900 hover:bg-zinc-850 text-zinc-300 hover:text-zinc-100 border border-zinc-750 rounded-md font-mono text-[11px] font-medium transition-all"
              title="Open Technical Help Centre, Glossary, and Specifications"
            >
              <BookOpen className="w-3.5 h-3.5 text-zinc-400" />
              <span>Help Centre</span>
            </button>
          )}

          {/* Exhibition Presentation Mode Button */}
          <button
            onClick={onOpenDemo}
            className="flex items-center space-x-1 px-2.5 py-1 bg-gradient-to-r from-emerald-600/30 to-cyan-600/30 hover:from-emerald-600/40 hover:to-cyan-600/40 text-emerald-300 border border-emerald-500/50 rounded-md font-mono text-[11px] font-bold transition-all shadow-sm cursor-pointer"
            title="Open Fullscreen Technical Exhibition & Presentation Mode [Esc to exit]"
          >
            <Activity className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
            <span>Presentation Mode</span>
          </button>

          {/* Top-Level COMSEC Readiness Status Pill (Task 07-02-04, D-15) */}
          {comsecStatus === 'READY' ? (
            <div
              className="flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-mono border border-cyan-500/40 bg-cyan-950/20 text-cyan-400 shadow-[0_0_10px_rgba(6,182,212,0.2)]"
              title="Post-Quantum Hybrid Cryptography Subsystem Active: ML-KEM-768 + Ephemeral X25519 Key Exchange Enabled"
            >
              <Lock className="w-3.5 h-3.5 text-cyan-400" />
              <span>PQC READY: ML-KEM-768</span>
            </div>
          ) : comsecStatus === 'ZEROIZED' ? (
            <div
              className="flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-mono border border-amber-500/40 bg-amber-950/30 text-amber-300 shadow-[0_0_10px_rgba(245,158,11,0.2)] animate-pulse"
              title="Station Cryptographic Keyrings Have Been Purged via Emergency Zeroization"
            >
              <Lock className="w-3.5 h-3.5 text-amber-400" />
              <span>COMSEC: ZEROIZED</span>
            </div>
          ) : (
            <div
              className="flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-mono border border-rose-500/40 bg-rose-950/30 text-rose-300 shadow-[0_0_10px_rgba(239,68,68,0.2)]"
              title="Cryptographic Keyring Not Found or Gateway Unreachable"
            >
              <Lock className="w-3.5 h-3.5 text-rose-400" />
              <span>KEYRING UNLOADED</span>
            </div>
          )}

          {/* Dual-Station Daemon Status HUD (D-03) */}
          <div className="flex items-center space-x-1.5">
            {/* Station Alpha Badge */}
            <div
              className={`font-mono text-[10px] px-2 py-0.5 rounded flex items-center space-x-1.5 transition-all ${
                effAlpha.healthy
                  ? 'bg-cyan-950/60 border border-cyan-800/80 text-cyan-300'
                  : 'bg-rose-950/70 border border-rose-600/70 text-rose-300 animate-pulse'
              }`}
              title={
                effAlpha.healthy
                  ? `Station Alpha Daemon Online (Port ${effAlpha.port}, ${effAlpha.dbPath} WAL)`
                  : `Station Alpha Daemon Offline (Port ${effAlpha.port})`
              }
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  effAlpha.healthy ? 'bg-cyan-400' : 'bg-rose-400 animate-ping'
                }`}
              />
              <span>
                ALPHA :{effAlpha.port} {effAlpha.healthy ? `• ${effAlpha.dbPath}` : '• OFFLINE'}
              </span>
            </div>

            {/* Station Bravo Badge */}
            <div
              className={`font-mono text-[10px] px-2 py-0.5 rounded flex items-center space-x-1.5 transition-all ${
                effBravo.healthy
                  ? 'bg-emerald-950/60 border border-emerald-800/80 text-emerald-300'
                  : 'bg-rose-950/70 border border-rose-600/70 text-rose-300 animate-pulse'
              }`}
              title={
                effBravo.healthy
                  ? `Station Bravo Daemon Online (Port ${effBravo.port}, ${effBravo.dbPath} WAL)`
                  : `Station Bravo Daemon Offline (Port ${effBravo.port})`
              }
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  effBravo.healthy ? 'bg-emerald-400' : 'bg-rose-400 animate-ping'
                }`}
              />
              <span>
                BRAVO :{effBravo.port} {effBravo.healthy ? `• ${effBravo.dbPath}` : '• OFFLINE'}
              </span>
            </div>
          </div>

          {/* Unified Gateway Status Pill */}
          <div
            className={`flex items-center space-x-1.5 px-2 py-0.5 rounded border font-mono ${
              isBackendHealthy
                ? 'bg-zinc-900 border-zinc-750 text-zinc-300'
                : 'bg-rose-950/40 border-rose-800/60 text-rose-400'
            }`}
            title="Unified Console Gateway (:5050)"
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isBackendHealthy ? 'bg-zinc-400' : 'bg-rose-400 animate-ping'
              }`}
            />
            <span className="text-[10px] font-medium">
              {isBackendHealthy ? 'GW :5050' : 'GW OFFLINE'}
            </span>
          </div>

          {/* Tactical Virtual Link Status Pill (D-02) */}
          {queueStats?.transport && (
            !queueStats.transport.is_online ? (
              <button
                onClick={() => setActiveTab('connectivity')}
                className="bg-rose-950/70 border border-rose-600/70 text-rose-300 font-mono text-[10px] font-bold px-2 py-1 rounded shadow-[0_0_12px_rgba(239,68,68,0.3)] animate-pulse flex items-center space-x-1 cursor-pointer transition-all hover:bg-rose-900/80"
                title="Virtual RF Link is severed. Click to manage channel in Connectivity view."
              >
                <WifiOff className="w-3 h-3 text-rose-400" />
                <span>[LINK SEVERED / AIR-GAP]</span>
              </button>
            ) : ((queueStats.transport.drop_rate || 0) > 0 || (queueStats.transport.latency_ms || 0) > 0) ? (
              <button
                onClick={() => setActiveTab('connectivity')}
                className="bg-amber-950/70 border border-amber-500/60 text-amber-300 font-mono text-[10px] font-bold px-2 py-1 rounded shadow-[0_0_12px_rgba(245,158,11,0.25)] flex items-center space-x-1 cursor-pointer transition-all hover:bg-amber-900/80"
                title="Virtual RF Channel is degraded with latency/packet loss. Click to inspect."
              >
                <Wifi className="w-3 h-3 text-amber-400 animate-pulse" />
                <span>[CHANNEL IMPAIRED ({Math.round((queueStats.transport.drop_rate || 0) * 100)}% LOSS)]</span>
              </button>
            ) : (
              <div
                className="bg-emerald-950/40 border border-emerald-800/60 text-emerald-400 font-mono text-[10px] font-semibold px-2 py-1 rounded flex items-center space-x-1"
                title="Virtual RF Channel is nominal and operating without impairments."
              >
                <Wifi className="w-3 h-3 text-emerald-400" />
                <span>[LINK NOMINAL]</span>
              </div>
            )
          )}

          {/* Persistent Local Outbox Counter Badge (D-06) */}
          {typeof localOutboxCount === 'number' && localOutboxCount > 0 && (
            <button
              onClick={onFlushOutbox}
              className="bg-amber-950/80 border border-amber-500/60 text-amber-300 font-mono text-[10px] font-bold px-2 py-1 rounded shadow-[0_0_10px_rgba(245,158,11,0.2)] hover:bg-amber-900 cursor-pointer flex items-center space-x-1 transition-all"
              title="Click to flush local offline outbox immediately via Web Locks API"
            >
              <Package className="w-3 h-3 text-amber-400" />
              <span>📦 {localOutboxCount} LOCAL QUEUED</span>
            </button>
          )}

          {/* Audio Squelch / Beep Toggle (D-18) */}
          <button
            onClick={() => {
              const muted = audioService.toggleMute()
              setIsMuted(muted)
            }}
            className={`p-1.5 rounded-md border transition-all ${
              isMuted
                ? 'bg-zinc-900 border-zinc-750 text-zinc-500 hover:text-zinc-300'
                : 'bg-emerald-950/40 border-emerald-800/60 text-emerald-400 hover:bg-emerald-900/40'
            }`}
            title={isMuted ? 'Tactical Audio Muted (Click to enable squelch & chime)' : 'Tactical Audio Active (Click to mute)'}
          >
            {isMuted ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
          </button>

          {/* User Session Profile Button */}
          {currentUser ? (
            <div className="flex items-center space-x-1 bg-zinc-900 border border-zinc-750 px-2 py-1 rounded-md">
              <UserIcon className="w-3 h-3 text-emerald-400" />
              <span className="font-mono text-zinc-200 text-[10px] font-semibold">{currentUser.username}</span>
              <button
                onClick={onLogout}
                className="ml-1 text-zinc-500 hover:text-rose-400 p-0.5 rounded transition-colors"
                title="Log out"
              >
                <LogOut className="w-3 h-3" />
              </button>
            </div>
          ) : (
            <button
              onClick={onOpenAuth}
              className="flex items-center space-x-1 px-2 py-1 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 rounded-md font-medium text-[10px]"
            >
              <LogIn className="w-3 h-3" />
              <span>Login</span>
            </button>
          )}
        </div>
      </div>

      {/* Primary Workstation Navigation Bar */}
      <div className="border-t border-zinc-850 bg-zinc-900/60 px-4 py-1.5 overflow-x-auto">
        <nav className="max-w-7xl mx-auto flex items-center space-x-1 text-xs font-mono whitespace-nowrap">
          <button
            onClick={() => setActiveTab('overview')}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              activeTab === 'overview'
                ? 'bg-zinc-800 text-emerald-400 font-bold shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            Overview
          </button>

          <button
            onClick={() => setActiveTab('topology')}
            className={`flex items-center space-x-1 px-2.5 py-1 rounded-md transition-colors ${
              activeTab === 'topology'
                ? 'bg-zinc-800 text-emerald-400 font-bold shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block animate-pulse" />
            <span>Link Topology</span>
          </button>

          <button
            onClick={() => setActiveTab('transmitter')}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              activeTab === 'transmitter'
                ? 'bg-zinc-800 text-emerald-400 font-bold shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            Transmitter
          </button>

          <button
            onClick={() => setActiveTab('receiver')}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              activeTab === 'receiver'
                ? 'bg-zinc-800 text-emerald-400 font-bold shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            Receiver
          </button>

          <button
            onClick={() => setActiveTab('analyser')}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              activeTab === 'analyser'
                ? 'bg-zinc-800 text-emerald-400 font-bold shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            Signal Analyser
          </button>

          <button
            onClick={() => setActiveTab('channel')}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              activeTab === 'channel'
                ? 'bg-zinc-800 text-emerald-400 font-bold shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            Channel Lab
          </button>

          <button
            onClick={() => setActiveTab('models')}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              activeTab === 'models'
                ? 'bg-zinc-800 text-emerald-400 font-bold shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            Model Lab
          </button>

          <button
            onClick={() => setActiveTab('experiments')}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              activeTab === 'experiments'
                ? 'bg-zinc-800 text-emerald-400 font-bold shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            Experiments
          </button>

          <button
            onClick={() => setActiveTab('pipeline')}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              activeTab === 'pipeline'
                ? 'bg-zinc-800 text-emerald-400 font-bold shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            Pipeline Flow
          </button>

          <span className="text-zinc-700 px-1">|</span>

          <button
            onClick={() => setActiveTab('messages')}
            className={`flex items-center space-x-1 px-2.5 py-1 rounded-md transition-colors ${
              activeTab === 'messages'
                ? 'bg-zinc-800 text-emerald-400 font-bold shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            <span>Tactical Messages</span>
            {queueStats && (queueStats.queued > 0 || queueStats.sending > 0) && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full text-[9px] bg-amber-500/20 text-amber-300 border border-amber-500/40">
                {queueStats.queued + queueStats.sending}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('connectivity')}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              activeTab === 'connectivity'
                ? 'bg-zinc-800 text-emerald-400 font-bold shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            Connectivity
          </button>

          <button
            onClick={() => setActiveTab('devices')}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              activeTab === 'devices'
                ? 'bg-zinc-800 text-emerald-400 font-bold shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            Devices
          </button>

          <button
            onClick={() => setActiveTab('diagnostics')}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              activeTab === 'diagnostics'
                ? 'bg-zinc-800 text-emerald-400 font-bold shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            Diagnostics
          </button>

          <button
            onClick={() => setActiveTab('research')}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              activeTab === 'research'
                ? 'bg-zinc-800 text-emerald-400 font-bold shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            Research Lab
          </button>

          <button
            onClick={() => setActiveTab('waveform')}
            className={`px-2.5 py-1 rounded-md transition-colors inline-flex items-center space-x-1 ${
              activeTab === 'waveform'
                ? 'bg-zinc-800 text-emerald-400 font-bold shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
            title="LPI-CGAN waveform next to a conventional reference"
          >
            <Waves className="w-3 h-3" />
            <span>Waveform Lab</span>
          </button>

          <button
            onClick={() => setActiveTab('security')}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              activeTab === 'security'
                ? 'bg-zinc-800 text-emerald-400 font-bold shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            Security
          </button>
        </nav>
      </div>
    </header>
  )
}

