import { Endpoint, Message, QueueStats, RelayNode } from '../../types'

export interface TopoStation {
  id: string
  label: string
  kind: 'alpha' | 'bravo'
  online: boolean
  queued: number
}

export interface TopoRelay {
  id: string
  label: string
  status: string
  battery: number
  storage: number
  position: [number, number, number]
  online: boolean
  failsafeCutoff: boolean
}

export interface TopoLink {
  online: boolean
  degraded: boolean
  queued: number
  delivered: number
  pending: number
  color: string
  mode: string
  label: string
}

export interface TopologyModel {
  alpha: TopoStation
  bravo: TopoStation
  relays: TopoRelay[]
  link: TopoLink
}

export const LINK_COLORS = {
  online: '#34d399', // emerald-400
  degraded: '#fbbf24', // amber-400
  offline: '#f87171', // red-400
}

const RELAY_X = [-3.6, 0, 3.6]
const RELAY_Z = [-2.2, 0, 2.2]

interface BuildParams {
  endpoints: Endpoint[]
  queueStats: QueueStats | null
  messages: Message[]
  relays: RelayNode[]
  activeTransport: { active_transport: string | null; is_live: boolean } | null
}

/**
 * Pure derivation of the 3D scene state from live backend data. Kept free of
 * three.js so it can be unit-reasoned and reused by the 2D fallback.
 */
export function buildTopologyModel({
  endpoints,
  queueStats,
  messages,
  relays,
  activeTransport,
}: BuildParams): TopologyModel {
  const transportOnline = queueStats?.transport?.is_online ?? true
  const retryWaiting = queueStats?.retry_waiting ?? 0
  const queued = queueStats?.queued ?? 0
  const delivered = queueStats?.delivered ?? 0

  const alphaEp = endpoints.find((e) => e.endpoint_id === 'endpoint-a')
  const bravoEp = endpoints.find((e) => e.endpoint_id === 'endpoint-b')

  const pending = messages.filter(
    (m) => m.current_state === 'QUEUED' || m.current_state === 'SENDING' || m.current_state === 'AWAITING_ACK',
  ).length

  const degraded = transportOnline && retryWaiting > 0
  const color = !transportOnline ? LINK_COLORS.offline : degraded ? LINK_COLORS.degraded : LINK_COLORS.online
  const mode = activeTransport?.is_live ? activeTransport.active_transport ?? 'LIVE' : 'SIMULATION'

  const mappedRelays: TopoRelay[] = relays.slice(0, 3).map((r, i) => {
    const battery = r.battery_level_pct ?? r.battery_percentage ?? 100
    const storage = r.storage_usage_pct ?? r.storage_used_pct ?? 0
    const failsafeCutoff =
      r.failsafe_cutoff_active ??
      (battery <= 5 || storage >= 98 || r.status === 'LOW_BATTERY' || r.status === 'STORAGE_FULL')
    return {
      id: r.node_id,
      label: r.display_name || r.node_id,
      status: r.status,
      battery,
      storage,
      online: (r.status === 'ONLINE' || r.status === 'STANDBY') && !failsafeCutoff,
      failsafeCutoff,
      position: [RELAY_X[i] ?? 0, 0, RELAY_Z[i] ?? 0],
    }
  })

  return {
    alpha: {
      id: 'endpoint-a',
      label: alphaEp?.display_name ?? 'STATION ALPHA',
      kind: 'alpha',
      online: transportOnline,
      queued,
    },
    bravo: {
      id: 'endpoint-b',
      label: bravoEp?.display_name ?? 'STATION BRAVO',
      kind: 'bravo',
      online: transportOnline,
      queued: delivered,
    },
    relays: mappedRelays,
    link: {
      online: transportOnline,
      degraded,
      queued,
      delivered,
      pending,
      color,
      mode,
      label: !transportOnline ? 'LINK DOWN' : degraded ? 'RETRYING' : mode,
    },
  }
}
