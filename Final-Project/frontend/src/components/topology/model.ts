import { Endpoint, Message, QueueStats, RelayNode, MeshTopologyData } from '../../types'

export interface TopoStation {
  id: string
  label: string
  kind: 'alpha' | 'bravo'
  online: boolean
  queued: number
  position: [number, number, number]
}

export interface TopoRelay {
  id: string
  label: string
  status: string
  battery: number
  storage: number
  position: [number, number, number]
  nodeType: string
  sector: string
  queueDepth: number
  online: boolean
  failsafeCutoff: boolean
}

export interface TopoLink {
  sourceId: string
  targetId: string
  sourcePos: [number, number, number]
  targetPos: [number, number, number]
  isActiveRoute: boolean
  isBroken: boolean
  rfTier: string
  distanceKm: number
  latencyMs?: number
  maxRangeKm?: number
  // Visual / legacy compatibility fields
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
  links: TopoLink[]
  link: TopoLink
  activePath: string[]
  totalHops: number
  estimatedLatencyMs: number
  routeStatus: string
}

export const LINK_COLORS = {
  online: '#34d399', // emerald-400
  degraded: '#fbbf24', // amber-400
  offline: '#f87171', // red-400
  activeCyan: '#06b6d4', // cyan-500
  dormantZinc: '#27272a', // zinc-800
  brokenRed: '#ef4444', // red-500
}

export const DEFAULT_NODE_POSITIONS: Record<string, [number, number, number]> = {
  'endpoint-a': [-9.0, 0.0, 0.0],
  'relay-ground-01': [-5.0, 0.0, -1.5],
  'relay-convoy-01': [0.0, 0.0, 1.0],
  'relay-ground-02': [5.0, 0.0, -1.5],
  'relay-uav-alpha': [-3.0, 4.5, 0.5],
  'relay-uav-bravo': [3.0, 6.0, -0.5],
  'relay-aerial-sim-01': [0.0, 5.0, 0.0],
  'endpoint-b': [9.0, 0.0, 0.0],
}

export const DEFAULT_NODE_TYPES: Record<string, string> = {
  'endpoint-a': 'FIXED_GATEWAY',
  'relay-ground-01': 'PORTABLE_GROUND',
  'relay-convoy-01': 'VEHICLE_GATEWAY',
  'relay-ground-02': 'PORTABLE_GROUND',
  'relay-uav-alpha': 'AERIAL_PAYLOAD_SIMULATED',
  'relay-uav-bravo': 'AERIAL_PAYLOAD_SIMULATED',
  'relay-aerial-sim-01': 'AERIAL_PAYLOAD_SIMULATED',
  'endpoint-b': 'FIXED_GATEWAY',
}

export const DEFAULT_SECTORS: Record<string, string> = {
  'endpoint-a': 'ALPHA_BASE',
  'relay-ground-01': 'ALPHA_SECTOR',
  'relay-convoy-01': 'CENTRAL_AXIS',
  'relay-ground-02': 'BRAVO_SECTOR',
  'relay-uav-alpha': 'WEST_AIRBORNE',
  'relay-uav-bravo': 'EAST_AIRBORNE',
  'relay-aerial-sim-01': 'STANDBY_AIRBORNE',
  'endpoint-b': 'BRAVO_BASE',
}

/**
 * Pure calculation helper for UAV orbital drift.
 * Counter-rotational trigonometric offsets around base anchor positions.
 */
export function computeUAVDrift(
  basePos: [number, number, number],
  time: number,
  isBravo: boolean
): [number, number, number] {
  if (isBravo) {
    return [
      basePos[0] + 0.45 * Math.cos(-0.3 * time),
      basePos[1],
      basePos[2] + 0.45 * Math.sin(-0.3 * time),
    ]
  }
  return [
    basePos[0] + 0.35 * Math.cos(0.4 * time),
    basePos[1],
    basePos[2] + 0.35 * Math.sin(0.4 * time),
  ]
}

interface BuildParams {
  endpoints: Endpoint[]
  queueStats: QueueStats | null
  messages: Message[]
  relays: RelayNode[]
  activeTransport: { active_transport: string | null; is_live: boolean } | null
  meshData?: MeshTopologyData | null
}

/**
 * Pure derivation of the 3D stratified mesh scene state from live backend data.
 * Supports ground relays (Y=0) and elevated aerial flight corridors (Y=+4.5, Y=+6.0).
 */
export function buildTopologyModel({
  endpoints,
  queueStats,
  messages,
  relays,
  activeTransport,
  meshData,
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

  // Map relays from meshData if available, otherwise from relays prop
  const nodeDict: Record<string, {
    status: string
    battery: number
    storage: number
    failsafeCutoff: boolean
    nodeType: string
    sector: string
    queueDepth: number
    position: [number, number, number]
    label: string
  }> = {}

  if (meshData && meshData.nodes && meshData.nodes.length > 0) {
    for (const n of meshData.nodes) {
      if (n.id === 'endpoint-a' || n.id === 'endpoint-b') continue
      const battery = n.battery_percentage ?? 100
      const storage = n.storage_used_pct ?? 0
      const failsafeCutoff =
        n.failsafe_cutoff_active ??
        (battery <= 5 || storage >= 98 || n.status === 'LOW_BATTERY' || n.status === 'STORAGE_FULL')
      const pos = n.position || DEFAULT_NODE_POSITIONS[n.id] || [0, 0, 0]
      nodeDict[n.id] = {
        status: n.status,
        battery,
        storage,
        failsafeCutoff,
        nodeType: n.node_type || DEFAULT_NODE_TYPES[n.id] || 'PORTABLE_GROUND',
        sector: n.sector || DEFAULT_SECTORS[n.id] || 'TACTICAL',
        queueDepth: n.queue_depth ?? 0,
        position: [pos[0], pos[1], pos[2]],
        label: n.display_name || n.id,
      }
    }
  } else {
    // Seed with all known named relays
    const seedIds = [
      'relay-ground-01',
      'relay-convoy-01',
      'relay-ground-02',
      'relay-uav-alpha',
      'relay-uav-bravo',
    ]

    for (const id of seedIds) {
      const match = relays.find((r) => r.node_id === id)
      const battery = match?.battery_level_pct ?? match?.battery_percentage ?? 100
      const storage = match?.storage_usage_pct ?? match?.storage_used_pct ?? 0
      const failsafeCutoff =
        match?.failsafe_cutoff_active ??
        (battery <= 5 || storage >= 98 || match?.status === 'LOW_BATTERY' || match?.status === 'STORAGE_FULL')
      const pos = DEFAULT_NODE_POSITIONS[id] || [0, 0, 0]
      nodeDict[id] = {
        status: match?.status ?? 'ONLINE',
        battery,
        storage,
        failsafeCutoff,
        nodeType: match?.node_type || DEFAULT_NODE_TYPES[id] || 'PORTABLE_GROUND',
        sector: DEFAULT_SECTORS[id] || 'TACTICAL',
        queueDepth: match?.queue_depth ?? match?.queued_bundles_count ?? 0,
        position: pos,
        label: match?.display_name || id,
      }
    }
  }

  const mappedRelays: TopoRelay[] = Object.entries(nodeDict).map(([id, info]) => ({
    id,
    label: info.label,
    status: info.status,
    battery: info.battery,
    storage: info.storage,
    position: info.position,
    nodeType: info.nodeType,
    sector: info.sector,
    queueDepth: info.queueDepth,
    online: (info.status === 'ONLINE' || info.status === 'STANDBY') && !info.failsafeCutoff,
    failsafeCutoff: info.failsafeCutoff,
  }))

  // Resolve Active Route & Path
  const activePath =
    meshData?.active_route?.path && meshData.active_route.path.length > 0
      ? meshData.active_route.path
      : ['endpoint-a', 'relay-uav-alpha', 'relay-uav-bravo', 'endpoint-b']

  const activeSet = new Set<string>()
  for (let i = 0; i < activePath.length - 1; i++) {
    activeSet.add(`${activePath[i]}->${activePath[i + 1]}`)
    activeSet.add(`${activePath[i + 1]}->${activePath[i]}`)
  }

  // Helper to get position of any node ID
  const getNodePos = (id: string): [number, number, number] => {
    if (id === 'endpoint-a') return DEFAULT_NODE_POSITIONS['endpoint-a']
    if (id === 'endpoint-b') return DEFAULT_NODE_POSITIONS['endpoint-b']
    if (nodeDict[id]) return nodeDict[id].position
    return DEFAULT_NODE_POSITIONS[id] || [0, 0, 0]
  }

  // Build Links
  const mappedLinks: TopoLink[] = []

  if (meshData && meshData.links && meshData.links.length > 0) {
    for (const l of meshData.links) {
      const srcPos = getNodePos(l.source)
      const tgtPos = getNodePos(l.target)
      const isActive = l.is_active_route || activeSet.has(`${l.source}->${l.target}`)
      const srcNode = nodeDict[l.source]
      const tgtNode = nodeDict[l.target]
      const isBroken =
        Boolean(l.is_broken) ||
        (srcNode ? srcNode.status === 'RF_JAMMED' || srcNode.status === 'FORCE_OFFLINE' || srcNode.failsafeCutoff : false) ||
        (tgtNode ? tgtNode.status === 'RF_JAMMED' || tgtNode.status === 'FORCE_OFFLINE' || tgtNode.failsafeCutoff : false)

      mappedLinks.push({
        sourceId: l.source,
        targetId: l.target,
        sourcePos: srcPos,
        targetPos: tgtPos,
        isActiveRoute: isActive,
        isBroken,
        rfTier: l.rf_tier,
        distanceKm: l.distance_km,
        latencyMs: l.latency_ms,
        maxRangeKm: l.max_range_km,
        online: !isBroken,
        degraded: false,
        queued: isActive ? queued : 0,
        delivered: isActive ? delivered : 0,
        pending: isActive ? pending : 0,
        color: isBroken ? LINK_COLORS.brokenRed : isActive ? LINK_COLORS.activeCyan : LINK_COLORS.dormantZinc,
        mode,
        label: `${l.source} - ${l.target}`,
      })
    }
  } else {
    // Default candidate topology mesh links
    const candidatePairs: [string, string, string, number][] = [
      ['endpoint-a', 'relay-ground-01', 'GROUND_GROUND', 10.0],
      ['relay-ground-01', 'relay-convoy-01', 'GROUND_GROUND', 13.9],
      ['relay-convoy-01', 'relay-ground-02', 'GROUND_GROUND', 13.9],
      ['relay-ground-02', 'endpoint-b', 'GROUND_GROUND', 10.0],
      ['endpoint-a', 'relay-uav-alpha', 'GROUND_UAV', 19.3],
      ['relay-uav-alpha', 'relay-uav-bravo', 'UAV_UAV', 15.6],
      ['relay-uav-bravo', 'endpoint-b', 'GROUND_UAV', 19.3],
      ['relay-uav-alpha', 'relay-ground-01', 'GROUND_UAV', 12.6],
      ['relay-uav-alpha', 'relay-convoy-01', 'GROUND_UAV', 13.7],
      ['relay-uav-bravo', 'relay-convoy-01', 'GROUND_UAV', 17.1],
      ['relay-uav-bravo', 'relay-ground-02', 'GROUND_UAV', 16.3],
    ]

    for (const [src, tgt, tier, dist] of candidatePairs) {
      const srcPos = getNodePos(src)
      const tgtPos = getNodePos(tgt)
      const isActive = activeSet.has(`${src}->${tgt}`)
      const srcNode = nodeDict[src]
      const tgtNode = nodeDict[tgt]
      const isBroken =
        (srcNode ? srcNode.status === 'RF_JAMMED' || srcNode.status === 'FORCE_OFFLINE' || srcNode.failsafeCutoff : false) ||
        (tgtNode ? tgtNode.status === 'RF_JAMMED' || tgtNode.status === 'FORCE_OFFLINE' || tgtNode.failsafeCutoff : false)

      mappedLinks.push({
        sourceId: src,
        targetId: tgt,
        sourcePos: srcPos,
        targetPos: tgtPos,
        isActiveRoute: isActive,
        isBroken,
        rfTier: tier,
        distanceKm: dist,
        latencyMs: 15,
        maxRangeKm: tier === 'UAV_UAV' ? 60.0 : tier === 'GROUND_UAV' ? 23.0 : 15.0,
        online: !isBroken,
        degraded: false,
        queued: isActive ? queued : 0,
        delivered: isActive ? delivered : 0,
        pending: isActive ? pending : 0,
        color: isBroken ? LINK_COLORS.brokenRed : isActive ? LINK_COLORS.activeCyan : LINK_COLORS.dormantZinc,
        mode,
        label: `${src} - ${tgt}`,
      })
    }
  }

  // Primary synthetic link for fallback compatibility
  const primaryLink: TopoLink = {
    sourceId: 'endpoint-a',
    targetId: 'endpoint-b',
    sourcePos: DEFAULT_NODE_POSITIONS['endpoint-a'],
    targetPos: DEFAULT_NODE_POSITIONS['endpoint-b'],
    isActiveRoute: true,
    isBroken: !transportOnline,
    rfTier: 'GROUND_UAV',
    distanceKm: 45.0,
    online: transportOnline,
    degraded,
    queued,
    delivered,
    pending,
    color,
    mode,
    label: !transportOnline ? 'LINK DOWN' : degraded ? 'RETRYING' : mode,
  }

  return {
    alpha: {
      id: 'endpoint-a',
      label: alphaEp?.display_name ?? 'STATION ALPHA',
      kind: 'alpha',
      online: transportOnline,
      queued,
      position: DEFAULT_NODE_POSITIONS['endpoint-a'],
    },
    bravo: {
      id: 'endpoint-b',
      label: bravoEp?.display_name ?? 'STATION BRAVO',
      kind: 'bravo',
      online: transportOnline,
      queued: delivered,
      position: DEFAULT_NODE_POSITIONS['endpoint-b'],
    },
    relays: mappedRelays,
    links: mappedLinks,
    link: primaryLink,
    activePath,
    totalHops: meshData?.active_route?.total_hops ?? Math.max(1, activePath.length - 1),
    estimatedLatencyMs: meshData?.active_route?.estimated_latency_ms ?? 35,
    routeStatus: meshData?.active_route?.route_status ?? (transportOnline ? 'OPTIMAL' : 'NO_ROUTE'),
  }
}
