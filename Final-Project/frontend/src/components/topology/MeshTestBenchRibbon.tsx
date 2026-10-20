import React from 'react'
import {
  Play,
  RotateCcw,
  Zap,
  Radio,
  ArrowRight,
  Clock,
  Send,
  AlertTriangle,
  X,
} from 'lucide-react'

interface MeshTestBenchRibbonProps {
  activePath: string[]
  totalHops: number
  estimatedLatencyMs: number
  convergenceMs: number | null
  diversionBanner: string | null
  onScenarioTrigger: (scenario: string) => Promise<void>
  onSimulateHop: () => Promise<void>
  onClearDiversion?: () => void
  isBusy: boolean
}

export const MeshTestBenchRibbon: React.FC<MeshTestBenchRibbonProps> = ({
  activePath,
  totalHops,
  estimatedLatencyMs,
  convergenceMs,
  diversionBanner,
  onScenarioTrigger,
  onSimulateHop,
  onClearDiversion,
  isBusy,
}) => {
  // Format readable node name for ribbon
  const formatNodeName = (id: string) => {
    switch (id) {
      case 'endpoint-a':
        return 'Alpha'
      case 'endpoint-b':
        return 'Bravo'
      case 'relay-ground-01':
        return 'Ground-01'
      case 'relay-convoy-01':
        return 'Convoy-01'
      case 'relay-ground-02':
        return 'Ground-02'
      case 'relay-uav-alpha':
        return 'UAV-Alpha'
      case 'relay-uav-bravo':
        return 'UAV-Bravo'
      case 'relay-aerial-sim-01':
        return 'Aerial-Sim'
      default:
        return id.replace('relay-', '')
    }
  }

  return (
    <div className="space-y-2">
      {/* Route Diversion Alert Banner (D-16) */}
      {diversionBanner && (
        <div className="p-2.5 rounded-lg border border-amber-500/80 bg-amber-950/60 shadow-[0_0_20px_rgba(245,158,11,0.25)] flex items-center justify-between animate-pulse text-amber-200 text-xs font-mono">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span className="font-bold tracking-wide">{diversionBanner}</span>
          </div>
          {onClearDiversion && (
            <button
              onClick={onClearDiversion}
              className="p-1 rounded text-amber-400 hover:text-amber-100 hover:bg-amber-900/60 transition-colors"
              title="Dismiss Alert"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      )}

      {/* Main Tactical Ribbon */}
      <div className="rounded-xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-950/90 p-3 shadow-md">
        {/* Top Status & Active Hop Indicator */}
        <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 mb-2.5 border-b border-slate-200 dark:border-zinc-800/80">
          <div className="flex items-center space-x-2">
            <div className="flex items-center space-x-1.5 px-2 py-0.5 rounded bg-cyan-950/50 border border-cyan-800/60 text-cyan-400 text-[11px] font-mono font-bold">
              <Radio className="w-3.5 h-3.5" />
              <span>ACTIVE DIJKSTRA ROUTE</span>
            </div>

            {/* Convergence Latency Badge */}
            {convergenceMs !== null && (
              <span className="px-2 py-0.5 rounded bg-emerald-950/70 border border-emerald-500/60 text-emerald-300 font-mono text-[10px] font-bold shadow-[0_0_10px_rgba(16,185,129,0.2)] flex items-center space-x-1">
                <Clock className="w-3 h-3 text-emerald-400" />
                <span>CONVERGED IN {convergenceMs.toFixed(1)} ms</span>
              </span>
            )}
          </div>

          {/* Hop Path Trail */}
          <div className="flex items-center space-x-1 text-xs font-mono text-slate-700 dark:text-zinc-300 overflow-x-auto py-0.5">
            {activePath.map((nodeId, idx) => (
              <React.Fragment key={idx}>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    nodeId === 'endpoint-a'
                      ? 'bg-cyan-100 text-cyan-900 border border-cyan-300 dark:bg-cyan-950/80 dark:border-cyan-600/70 dark:text-cyan-300'
                      : nodeId === 'endpoint-b'
                      ? 'bg-emerald-100 text-emerald-900 border border-emerald-300 dark:bg-emerald-950/80 dark:border-emerald-600/70 dark:text-emerald-300'
                      : 'bg-slate-100 text-slate-800 border border-slate-300 dark:bg-zinc-900 dark:border-zinc-700 dark:text-zinc-200'
                  }`}
                >
                  {formatNodeName(nodeId)}
                </span>
                {idx < activePath.length - 1 && (
                  <ArrowRight className="w-3 h-3 text-cyan-500 shrink-0" />
                )}
              </React.Fragment>
            ))}
            <span className="ml-2 text-[10px] text-slate-500 dark:text-zinc-500">
              ({totalHops} {totalHops === 1 ? 'hop' : 'hops'} · ~{estimatedLatencyMs}ms)
            </span>
          </div>
        </div>

        {/* Operational Drill Buttons & Controls */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] font-mono text-slate-500 dark:text-zinc-500 mr-1 uppercase tracking-wider">
              Tactical Drills:
            </span>

            {/* Scenario 1: UAV-Alpha Signal Lost */}
            <button
              onClick={() => onScenarioTrigger('scenario_1_uav_signal_lost')}
              disabled={isBusy}
              className="px-2.5 py-1 rounded bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/40 dark:hover:bg-rose-900/60 border border-rose-300 dark:border-rose-800/60 text-rose-800 dark:text-rose-300 font-mono text-[11px] font-semibold transition-all flex items-center space-x-1 cursor-pointer disabled:opacity-40"
              title="Kills relay-uav-alpha battery (8%) and forces diversion to ground convoy path"
            >
              <Zap className="w-3 h-3 text-rose-500 dark:text-rose-400" />
              <span>Scenario 1: UAV-Alpha Lost</span>
            </button>

            {/* Scenario 2: Ground Relays Jammed */}
            <button
              onClick={() => onScenarioTrigger('scenario_2_ground_relays_jammed')}
              disabled={isBusy}
              className="px-2.5 py-1 rounded bg-amber-50 hover:bg-amber-100 dark:bg-amber-950/40 dark:hover:bg-amber-900/60 border border-amber-300 dark:border-amber-800/60 text-amber-800 dark:text-amber-300 font-mono text-[11px] font-semibold transition-all flex items-center space-x-1 cursor-pointer disabled:opacity-40"
              title="Sets ground relays to RF_JAMMED, compelling all-aerial corridor"
            >
              <AlertTriangle className="w-3 h-3 text-amber-500 dark:text-amber-400" />
              <span>Scenario 2: Ground Relays Jammed</span>
            </button>

            {/* Scenario 3: Convoy Mobile Breakout */}
            <button
              onClick={() => onScenarioTrigger('scenario_3_convoy_breakout')}
              disabled={isBusy}
              className="px-2.5 py-1 rounded bg-sky-50 hover:bg-sky-100 dark:bg-sky-950/40 dark:hover:bg-sky-900/60 border border-sky-300 dark:border-sky-800/60 text-sky-800 dark:text-sky-300 font-mono text-[11px] font-semibold transition-all flex items-center space-x-1 cursor-pointer disabled:opacity-40"
              title="Disables UAVs and shifts convoy to extended perimeter for 4-hop relaying"
            >
              <Play className="w-3 h-3 text-sky-500 dark:text-sky-400" />
              <span>Scenario 3: Convoy Breakout</span>
            </button>

            {/* Reset All to Nominal */}
            <button
              onClick={() => onScenarioTrigger('reset_nominal')}
              disabled={isBusy}
              className="px-2.5 py-1 rounded bg-slate-100 hover:bg-slate-200 dark:bg-zinc-900 dark:hover:bg-zinc-800 border border-slate-300 dark:border-zinc-700 text-slate-800 dark:text-zinc-300 font-mono text-[11px] font-semibold transition-all flex items-center space-x-1 cursor-pointer disabled:opacity-40"
              title="Restores all relays to ONLINE nominal status"
            >
              <RotateCcw className="w-3 h-3 text-emerald-500 dark:text-emerald-400" />
              <span>Reset Nominal</span>
            </button>
          </div>

          {/* Quick Route Simulation */}
          <button
            onClick={onSimulateHop}
            disabled={isBusy}
            className="px-3 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-white font-mono text-[11px] font-bold transition-all shadow-md flex items-center space-x-1.5 cursor-pointer disabled:opacity-40"
            title="Simulate store-and-forward hop delivery with custody HMAC verification"
          >
            <Send className="w-3 h-3 text-white" />
            <span>{isBusy ? 'CONVERGING…' : 'Simulate Hop Delivery'}</span>
          </button>
        </div>
      </div>
    </div>
  )
}
export default MeshTestBenchRibbon
