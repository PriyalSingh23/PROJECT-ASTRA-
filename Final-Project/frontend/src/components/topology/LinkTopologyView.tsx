import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Html, Line } from '@react-three/drei'
import * as THREE from 'three'
import {
  Radio,
  Eye,
  Layers,
  Compass,
  Zap,
  RotateCcw,
  Sparkles,
} from 'lucide-react'
import { api } from '../../services/api'
import { Endpoint, Message, QueueStats, RelayNode, MeshTopologyData } from '../../types'
import { TopologyModel, TopoRelay, buildTopologyModel, computeUAVDrift, LINK_COLORS } from './model'
import { TopologyFallback } from './TopologyFallback'
import { ErrorBoundary } from '../ErrorBoundary'
import { MessageDrawer, DrawerStation } from '../MessageDrawer'
import { AnomalyStrip } from '../research/AnomalyStrip'
import { useAnomalyReport } from '../research/useAnomalyReport'
import { RelayInspectorDrawer } from './RelayInspectorDrawer'
import { MeshTestBenchRibbon } from './MeshTestBenchRibbon'

interface LinkTopologyViewProps {
  endpoints: Endpoint[]
  messages: Message[]
  queueStats: QueueStats | null
  isBackendHealthy: boolean
}

// ---------------------------------------------------------------------------
// Stratified 3D Scene Primitives
// ---------------------------------------------------------------------------

/** Station Node (Alpha or Bravo base) */
const StationNode: React.FC<{
  position: [number, number, number]
  label: string
  sub: string
  color: string
  isAlpha: boolean
  onSelect?: () => void
}> = ({ position, label, sub, color, isAlpha, onSelect }) => {
  const meshRef = useRef<THREE.Mesh>(null)
  const ringRef = useRef<THREE.Mesh>(null)

  useFrame(({ clock }) => {
    if (meshRef.current) {
      meshRef.current.scale.setScalar(1 + Math.sin(clock.elapsedTime * 2.5) * 0.04)
    }
    if (ringRef.current) {
      ringRef.current.rotation.z = clock.elapsedTime * (isAlpha ? 0.6 : -0.6)
    }
  })

  return (
    <group position={position}>
      <mesh
        ref={meshRef}
        onClick={
          onSelect
            ? (e) => {
                e.stopPropagation()
                onSelect()
              }
            : undefined
        }
        onPointerOver={onSelect ? () => { document.body.style.cursor = 'pointer' } : undefined}
        onPointerOut={onSelect ? () => { document.body.style.cursor = 'auto' } : undefined}
      >
        <sphereGeometry args={[0.65, 32, 32]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.8}
          roughness={0.2}
          metalness={0.6}
        />
      </mesh>

      {/* Orbiting Radar Pulse Ring */}
      <mesh ref={ringRef} rotation={[Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.95, 1.15, 48]} />
        <meshBasicMaterial color={color} transparent opacity={0.6} side={THREE.DoubleSide} />
      </mesh>

      {/* Floating Tactical HUD Label */}
      <Html center distanceFactor={14} position={[0, 1.45, 0]} pointerEvents="none">
        <div className="px-2 py-1 rounded border border-zinc-700 bg-zinc-950/90 text-center whitespace-nowrap shadow-lg backdrop-blur-sm">
          <div className="text-[11px] font-mono font-bold text-zinc-100 tracking-wider flex items-center justify-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ backgroundColor: color }} />
            <span>{label}</span>
          </div>
          <div className="text-[9px] font-mono text-zinc-400 mt-0.5">{sub}</div>
        </div>
      </Html>
    </group>
  )
}

/** Aerial UAV Relay Marker with continuous orbital drift */
const UAVRelayMarker: React.FC<{
  relay: TopoRelay
  onSelect: () => void
}> = ({ relay, onSelect }) => {
  const groupRef = useRef<THREE.Group>(null)
  const isBravo = relay.id.includes('bravo')

  useFrame(({ clock }) => {
    if (groupRef.current) {
      const drifted = computeUAVDrift(relay.position, clock.elapsedTime, isBravo)
      groupRef.current.position.set(drifted[0], drifted[1], drifted[2])
      groupRef.current.rotation.y = clock.elapsedTime * 0.75
    }
  })

  const isAlarm = relay.status === 'RF_JAMMED' || relay.status === 'FORCE_OFFLINE' || relay.failsafeCutoff
  const isLowBat = relay.status === 'LOW_BATTERY' || relay.battery <= 15
  const color = isAlarm ? '#f43f5e' : isLowBat ? '#f59e0b' : '#38bdf8'

  return (
    <group ref={groupRef} position={relay.position}>
      <mesh
        onClick={(e) => {
          e.stopPropagation()
          onSelect()
        }}
        onPointerOver={() => { document.body.style.cursor = 'pointer' }}
        onPointerOut={() => { document.body.style.cursor = 'auto' }}
      >
        <octahedronGeometry args={[0.42, 0]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={isAlarm ? 0.9 : 0.6}
          roughness={0.3}
          metalness={0.7}
        />
      </mesh>

      {/* Orbit corridor beacon halo */}
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.6, 0.7, 32]} />
        <meshBasicMaterial color={color} transparent opacity={0.3} side={THREE.DoubleSide} />
      </mesh>

      {/* Floating Tactical HUD Pill */}
      <Html center distanceFactor={15} position={[0, 0.95, 0]} pointerEvents="none">
        <div className={`px-2 py-0.5 rounded border text-center whitespace-nowrap shadow-md backdrop-blur-sm ${
          isAlarm
            ? 'border-rose-600/80 bg-rose-950/90 text-rose-200 animate-pulse'
            : isLowBat
            ? 'border-amber-600/80 bg-amber-950/90 text-amber-200'
            : 'border-zinc-700 bg-zinc-950/85 text-zinc-200'
        }`}>
          <div className="text-[10px] font-mono font-bold tracking-tight">
            {relay.label}
          </div>
          <div className="text-[9px] font-mono text-zinc-400 flex items-center justify-center space-x-1 mt-0.5">
            <span className={relay.battery <= 15 ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
              {relay.battery}%
            </span>
            <span>·</span>
            <span className="text-cyan-400">Q:{relay.queueDepth}</span>
            <span>·</span>
            <span className="text-zinc-500">{(relay.position[1] * 2.5).toFixed(1)}km</span>
          </div>
          {isAlarm && (
            <div className="text-[8px] font-mono font-bold text-rose-300 uppercase mt-0.5">
              [{relay.status}]
            </div>
          )}
        </div>
      </Html>
    </group>
  )
}

/** Ground Relay Marker (Stationary Beacon or Mobile Convoy) at Y=0 */
const GroundRelayMarker: React.FC<{
  relay: TopoRelay
  onSelect: () => void
}> = ({ relay, onSelect }) => {
  const meshRef = useRef<THREE.Mesh>(null)
  const isConvoy = relay.nodeType === 'VEHICLE_GATEWAY' || relay.id.includes('convoy')

  useFrame(({ clock }) => {
    if (meshRef.current) {
      meshRef.current.rotation.y = clock.elapsedTime * (isConvoy ? 0.9 : 0.4)
    }
  })

  const isAlarm = relay.status === 'RF_JAMMED' || relay.status === 'FORCE_OFFLINE' || relay.failsafeCutoff
  const isLowBat = relay.status === 'LOW_BATTERY' || relay.battery <= 15
  const color = isAlarm
    ? '#f43f5e'
    : isConvoy
    ? '#f59e0b'
    : isLowBat
    ? '#fbbf24'
    : '#10b981'

  return (
    <group position={relay.position}>
      <mesh
        ref={meshRef}
        onClick={(e) => {
          e.stopPropagation()
          onSelect()
        }}
        onPointerOver={() => { document.body.style.cursor = 'pointer' }}
        onPointerOut={() => { document.body.style.cursor = 'auto' }}
      >
        {isConvoy ? (
          <boxGeometry args={[0.55, 0.4, 0.55]} />
        ) : (
          <cylinderGeometry args={[0.28, 0.38, 0.5, 6]} />
        )}
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={isAlarm ? 0.9 : 0.55}
          roughness={0.4}
          metalness={0.5}
        />
      </mesh>

      {/* Floating Tactical HUD Pill */}
      <Html center distanceFactor={15} position={[0, 0.85, 0]} pointerEvents="none">
        <div className={`px-2 py-0.5 rounded border text-center whitespace-nowrap shadow-md backdrop-blur-sm ${
          isAlarm
            ? 'border-rose-600/80 bg-rose-950/90 text-rose-200 animate-pulse'
            : isConvoy
            ? 'border-amber-600/70 bg-zinc-950/90 text-amber-200'
            : 'border-zinc-700 bg-zinc-950/85 text-zinc-200'
        }`}>
          <div className="text-[10px] font-mono font-bold tracking-tight">
            {relay.label}
          </div>
          <div className="text-[9px] font-mono text-zinc-400 flex items-center justify-center space-x-1 mt-0.5">
            <span className={relay.battery <= 15 ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
              {relay.battery}%
            </span>
            <span>·</span>
            <span className="text-cyan-400">Q:{relay.queueDepth}</span>
            <span>·</span>
            <span className="text-zinc-500">GROUND</span>
          </div>
          {isAlarm && (
            <div className="text-[8px] font-mono font-bold text-rose-300 uppercase mt-0.5">
              [{relay.status}]
            </div>
          )}
        </div>
      </Html>
    </group>
  )
}

/** Animated Photon Pulses traveling continuously along the active vector path */
const PhotonPulses: React.FC<{
  points: [number, number, number][]
  count?: number
  color?: string
}> = ({ points, count = 5, color = '#38bdf8' }) => {
  const refs = useRef<(THREE.Mesh | null)[]>([])

  const curve = useMemo(() => {
    if (points.length < 2) return null
    return new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p)), false, 'catmullrom', 0.1)
  }, [points])

  useFrame(({ clock }) => {
    if (!curve) return
    const n = Math.max(count, 1)
    refs.current.forEach((mesh, idx) => {
      if (!mesh) return
      const t = (clock.elapsedTime * 0.28 + idx / n) % 1.0
      const pos = curve.getPointAt(t)
      mesh.position.set(pos.x, pos.y, pos.z)
    })
  })

  if (!curve) return null

  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <mesh
          key={i}
          ref={(el) => {
            refs.current[i] = el
          }}
        >
          <sphereGeometry args={[0.13, 16, 16]} />
          <meshBasicMaterial color={color} />
        </mesh>
      ))}
    </>
  )
}

/** Radar Ground Grid Sweep */
const GroundRadarSweep: React.FC<{ position: [number, number, number]; color: string }> = ({
  position,
  color,
}) => {
  const ref = useRef<THREE.Mesh>(null)
  useFrame((_, dt) => {
    if (ref.current) ref.current.rotation.z += dt * 1.2
  })
  return (
    <group position={position} rotation={[-Math.PI / 2, 0, 0]}>
      <mesh>
        <ringGeometry args={[4.2, 4.3, 64]} />
        <meshBasicMaterial color={color} transparent opacity={0.3} side={THREE.DoubleSide} />
      </mesh>
      <mesh ref={ref}>
        <circleGeometry args={[4.2, 48, 0, Math.PI / 4]} />
        <meshBasicMaterial color={color} transparent opacity={0.12} side={THREE.DoubleSide} />
      </mesh>
    </group>
  )
}

/** Camera Controller for Smooth Navigation & Quick-View Presets */
const CameraController: React.FC<{
  targetCam: [number, number, number]
  targetLookAt: [number, number, number]
  controlsRef: React.RefObject<any>
}> = ({ targetCam, targetLookAt, controlsRef }) => {
  useFrame(({ camera }) => {
    if (controlsRef.current) {
      camera.position.lerp(new THREE.Vector3(...targetCam), 0.08)
      controlsRef.current.target.lerp(new THREE.Vector3(...targetLookAt), 0.08)
      controlsRef.current.update()
    }
  })
  return null
}

// ---------------------------------------------------------------------------
// 3D Scene Root
// ---------------------------------------------------------------------------
const StratifiedMeshScene: React.FC<{
  model: TopologyModel
  onSelectRelay: (relay: TopoRelay) => void
  onSelectStation?: (station: DrawerStation) => void
  cameraPreset: { cam: [number, number, number]; target: [number, number, number] }
  controlsRef: React.RefObject<any>
}> = ({ model, onSelectRelay, onSelectStation, cameraPreset, controlsRef }) => {
  const { alpha, bravo, relays, links, activePath } = model

  // Active path vector coordinates
  const activePathPoints = useMemo<[number, number, number][]>(() => {
    const points: [number, number, number][] = []
    for (const nodeId of activePath) {
      if (nodeId === 'endpoint-a') {
        points.push(alpha.position)
      } else if (nodeId === 'endpoint-b') {
        points.push(bravo.position)
      } else {
        const r = relays.find((x) => x.id === nodeId)
        if (r) points.push(r.position)
      }
    }
    return points.length >= 2 ? points : [alpha.position, bravo.position]
  }, [activePath, alpha.position, bravo.position, relays])

  // Partition links: active vs dormant vs broken
  const dormantLinks = useMemo(() => links.filter((l) => !l.isActiveRoute && !l.isBroken), [links])
  const activeLinks = useMemo(() => links.filter((l) => l.isActiveRoute && !l.isBroken), [links])
  const brokenLinks = useMemo(() => links.filter((l) => l.isBroken), [links])

  return (
    <>
      <ambientLight intensity={0.4} />
      <directionalLight position={[10, 18, 12]} intensity={1.2} />
      <pointLight position={alpha.position} intensity={18} distance={16} color="#06b6d4" />
      <pointLight position={bravo.position} intensity={18} distance={16} color="#10b981" />

      {/* Dual Tactical Grid: Ground Floor and Aerial Altitude Guide */}
      <gridHelper args={[48, 48, '#1e293b', '#0f172a']} position={[0, -0.05, 0]} />

      {/* Ground Radar Sweeps at Alpha and Bravo */}
      <GroundRadarSweep position={[alpha.position[0], 0, alpha.position[2]]} color="#06b6d4" />
      <GroundRadarSweep position={[bravo.position[0], 0, bravo.position[2]]} color="#10b981" />

      {/* 1. Dormant Candidate Mesh Links (Subtle Translucent Zinc Lines) */}
      {dormantLinks.map((l, i) => (
        <Line
          key={`dormant-${i}`}
          points={[l.sourcePos, l.targetPos]}
          color="#3f3f46"
          lineWidth={1.2}
          dashed
          dashSize={0.4}
          gapSize={0.3}
          transparent
          opacity={0.3}
        />
      ))}

      {/* 2. Active Multi-Hop Forwarding Vectors (Glowing Neon Cyan Laser) */}
      {activeLinks.map((l, i) => (
        <Line
          key={`active-${i}`}
          points={[l.sourcePos, l.targetPos]}
          color="#06b6d4"
          lineWidth={3.8}
          transparent
          opacity={0.95}
        />
      ))}

      {/* 3. Broken Impaired Links (Dashed Red Strikethrough) */}
      {brokenLinks.map((l, i) => (
        <Line
          key={`broken-${i}`}
          points={[l.sourcePos, l.targetPos]}
          color="#ef4444"
          lineWidth={2.8}
          dashed
          dashSize={0.3}
          gapSize={0.25}
          transparent
          opacity={0.9}
        />
      ))}

      {/* Traveling Animated Photons along Active Path */}
      {activePathPoints.length >= 2 && (
        <PhotonPulses points={activePathPoints} count={5} color="#38bdf8" />
      )}

      {/* Station Alpha Node */}
      <StationNode
        position={alpha.position}
        label={alpha.label}
        sub={`OUTBOX: ${alpha.queued}`}
        color="#06b6d4"
        isAlpha={true}
        onSelect={onSelectStation ? () => onSelectStation({ id: alpha.id, label: alpha.label }) : undefined}
      />

      {/* Station Bravo Node */}
      <StationNode
        position={bravo.position}
        label={bravo.label}
        sub={`INBOX: ${bravo.queued}`}
        color="#10b981"
        isAlpha={false}
        onSelect={onSelectStation ? () => onSelectStation({ id: bravo.id, label: bravo.label }) : undefined}
      />

      {/* Stratified Relay Markers */}
      {relays.map((r) => {
        const isAerial = r.nodeType === 'AERIAL_PAYLOAD_SIMULATED' || r.id.includes('uav')
        if (isAerial) {
          return (
            <UAVRelayMarker
              key={r.id}
              relay={r}
              onSelect={() => onSelectRelay(r)}
            />
          )
        }
        return (
          <GroundRelayMarker
            key={r.id}
            relay={r}
            onSelect={() => onSelectRelay(r)}
          />
        )
      })}

      {/* Orbit Navigation Controls */}
      <OrbitControls
        ref={controlsRef}
        enablePan={true}
        enableDamping={true}
        dampingFactor={0.05}
        minDistance={6}
        maxDistance={40}
        maxPolarAngle={Math.PI / 2.05}
      />

      <CameraController
        targetCam={cameraPreset.cam}
        targetLookAt={cameraPreset.target}
        controlsRef={controlsRef}
      />
    </>
  )
}

// ---------------------------------------------------------------------------
// Main LinkTopologyView Component
// ---------------------------------------------------------------------------
export const LinkTopologyView: React.FC<LinkTopologyViewProps> = ({
  endpoints,
  messages,
  queueStats,
  isBackendHealthy,
}) => {
  const [relays, setRelays] = useState<RelayNode[]>([])
  const [meshData, setMeshData] = useState<MeshTopologyData | null>(null)
  const [selectedRelay, setSelectedRelay] = useState<TopoRelay | null>(null)
  const [drawerStation, setDrawerStation] = useState<DrawerStation | null>(null)
  const [activeTransport, setActiveTransport] = useState<{
    active_transport: string | null
    is_live: boolean
  } | null>(null)
  const [isBusy, setIsBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [diversionBanner, setDiversionBanner] = useState<string | null>(null)
  const [convergenceMs, setConvergenceMs] = useState<number | null>(null)

  // Camera preset state
  const controlsRef = useRef<any>(null)
  const [cameraPreset, setCameraPreset] = useState<{
    cam: [number, number, number]
    target: [number, number, number]
  }>({
    cam: [0, 16, 22],
    target: [0, 2, 0],
  })

  const { report: anomalyReport, loading: anomalyLoading, error: anomalyError, refresh: refreshAnomalies } =
    useAnomalyReport(30000)

  // Load topology and mesh data
  const loadTopology = useCallback(async () => {
    try {
      const [r, a, m] = await Promise.all([
        api.getRelays(),
        api.getActiveTransport().catch(() => ({ active_transport: null, is_live: false })),
        api.getMeshTopology().catch(() => null),
      ])
      setRelays(r)
      setActiveTransport({ active_transport: a.active_transport, is_live: a.is_live })
      if (m) {
        setMeshData(m)
      }
    } catch {
      /* Keep last known state on backend disconnect */
    }
  }, [])

  useEffect(() => {
    loadTopology()
    const interval = setInterval(loadTopology, 3500)
    return () => clearInterval(interval)
  }, [loadTopology])

  const model = useMemo(
    () => buildTopologyModel({ endpoints, queueStats, messages, relays, activeTransport, meshData }),
    [endpoints, queueStats, messages, relays, activeTransport, meshData]
  )

  // Trigger operational drill scenario
  const handleScenarioTrigger = async (scenario: string) => {
    setIsBusy(true)
    const t0 = performance.now()
    try {
      const res = await api.triggerMeshScenario(scenario)
      const elapsed = res.convergence_latency_ms || Math.max(0.5, performance.now() - t0)
      setConvergenceMs(elapsed)
      if (res.reroute_event && res.reroute_event.trim() !== '') {
        setDiversionBanner(res.reroute_event)
      } else if (res.new_path && res.new_path.length > 0) {
        setDiversionBanner(`[MESH REROUTE: Converged to ${res.new_path.join(' -> ')} in ${elapsed.toFixed(1)}ms]`)
      }
      await loadTopology()
    } catch (err) {
      setNotice(`Failed to execute scenario: ${String(err)}`)
    } finally {
      setIsBusy(false)
    }
  }

  // Simulate hop delivery
  const handleSimulateHop = async () => {
    setIsBusy(true)
    try {
      const res = await api.simulateRoute()
      setNotice(`Simulated hop delivery across path: ${res.path?.join(' -> ')} (Status: ${res.status})`)
      await loadTopology()
    } catch (err) {
      setNotice(`Simulation error: ${String(err)}`)
    } finally {
      setIsBusy(false)
    }
  }

  // Toggle Live hardware transport
  const toggleLive = async () => {
    setIsBusy(true)
    setNotice(null)
    try {
      const next = activeTransport?.is_live ? null : 'motorola-mototrbo-01'
      const res = await api.setActiveTransport(next)
      setActiveTransport({ active_transport: res.active_transport, is_live: res.is_live })
      setNotice(
        next
          ? `Outbound path set to ${next}. Hardware transmits only when MOTOROLA_RADIO_APPROVED=true (dry-run otherwise).`
          : 'Outbound path returned to the simulated link.'
      )
    } catch (e) {
      setNotice(`Could not change outbound path: ${String(e)}`)
    } finally {
      setIsBusy(false)
    }
  }

  // Camera Quick-View Preset triggers
  const setPresetTheater = () => setCameraPreset({ cam: [0, 16, 22], target: [0, 2, 0] })
  const setPresetUAV = () => setCameraPreset({ cam: [0, 9, 12], target: [0, 5, 0] })
  const setPresetVector = () => setCameraPreset({ cam: [-4, 7, 10], target: [0, 2, 0] })
  const setPresetGround = () => setCameraPreset({ cam: [0, 2, 16], target: [0, 0, 0] })

  return (
    <div className="space-y-3">
      {/* Header + Link status */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-sm font-mono font-bold text-zinc-100 tracking-wide">
                STRATIFIED 3D AD-HOC MESH ROUTING
              </h2>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-950/60 border border-cyan-500/60 text-cyan-300">
                MULTI-FACTOR DIJKSTRA
              </span>
            </div>
            <p className="text-[11px] text-zinc-400 mt-0.5">
              Dual-layer ad-hoc network: ground relays (Y=0) & aerial UAV flight corridors (Y=+4.5, Y=+6.0).
            </p>
          </div>

          <div className="flex items-center space-x-3 text-[11px] font-mono">
            <span className="inline-flex items-center space-x-1">
              <span className="w-2 h-2 rounded-full inline-block bg-[#06b6d4]" />
              <span className="text-zinc-300">Active Laser</span>
            </span>
            <span className="inline-flex items-center space-x-1">
              <span className="w-2 h-2 rounded-full inline-block bg-[#3f3f46]" />
              <span className="text-zinc-500">Dormant RF</span>
            </span>
            <span className="inline-flex items-center space-x-1">
              <span className="w-2 h-2 rounded-full inline-block bg-[#ef4444]" />
              <span className="text-rose-400">Broken / Jammed</span>
            </span>
            <span className="text-zinc-600">|</span>
            <span className={model.routeStatus === 'OPTIMAL' ? 'text-cyan-400 font-bold' : 'text-amber-400 font-bold'}>
              {model.routeStatus}
            </span>
          </div>
        </div>

        {/* Outbound path & hardware mode */}
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-zinc-800 pt-3">
          <div className="text-[11px] font-mono text-zinc-400">
            Outbound gateway:{' '}
            <span className={activeTransport?.is_live ? 'text-amber-400 font-bold' : 'text-cyan-400 font-bold'}>
              {activeTransport?.is_live ? activeTransport.active_transport : 'SIMULATION'}
            </span>
            <span className="mx-2 text-zinc-700">·</span>
            Active Hops <span className="text-cyan-300 font-bold">{model.totalHops}</span>
            <span className="mx-2 text-zinc-700">·</span>
            Queued <span className="text-zinc-200">{model.link.queued}</span>
            <span className="mx-2 text-zinc-700">·</span>
            Delivered <span className="text-zinc-200">{model.link.delivered}</span>
          </div>
          <button
            onClick={toggleLive}
            disabled={isBusy || !isBackendHealthy}
            className={`px-3 py-1.5 rounded-md text-[11px] font-mono font-bold transition-colors disabled:opacity-40 cursor-pointer ${
              activeTransport?.is_live
                ? 'bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-500/40'
                : 'bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 border border-emerald-500/40'
            }`}
          >
            {isBusy ? 'SWITCHING…' : activeTransport?.is_live ? 'RETURN TO SIMULATION' : 'GO LIVE (MOTOROLA)'}
          </button>
        </div>
        {notice && <div className="mt-2 text-[11px] font-mono text-amber-400">{notice}</div>}
      </div>

      {/* 3D Canvas with 4 Tactical Quick-View Presets */}
      <div className="relative rounded-lg border border-zinc-800 bg-zinc-950 overflow-hidden">
        {/* Top-Right Camera Quick-View Presets Overlay */}
        <div className="absolute top-3 right-3 z-20 flex flex-wrap items-center gap-1.5 bg-zinc-950/80 p-1 rounded-md border border-zinc-800/80 backdrop-blur-md">
          <button
            onClick={setPresetTheater}
            className="px-2 py-1 rounded text-[10px] font-mono text-zinc-300 hover:text-white hover:bg-zinc-800 transition-colors flex items-center space-x-1"
            title="Theater Overview [0, 16, 22]"
          >
            <Eye className="w-3 h-3 text-cyan-400" />
            <span>Theater Overview</span>
          </button>
          <button
            onClick={setPresetUAV}
            className="px-2 py-1 rounded text-[10px] font-mono text-zinc-300 hover:text-white hover:bg-zinc-800 transition-colors flex items-center space-x-1"
            title="Focus UAV Flight Corridors [0, 9, 12]"
          >
            <Compass className="w-3 h-3 text-sky-400" />
            <span>UAV Corridors</span>
          </button>
          <button
            onClick={setPresetVector}
            className="px-2 py-1 rounded text-[10px] font-mono text-zinc-300 hover:text-white hover:bg-zinc-800 transition-colors flex items-center space-x-1"
            title="Forwarding Vector Tracking [-4, 7, 10]"
          >
            <Sparkles className="w-3 h-3 text-amber-400" />
            <span>Vector Tracking</span>
          </button>
          <button
            onClick={setPresetGround}
            className="px-2 py-1 rounded text-[10px] font-mono text-zinc-300 hover:text-white hover:bg-zinc-800 transition-colors flex items-center space-x-1"
            title="Ground Axis Perspective [0, 2, 16]"
          >
            <Layers className="w-3 h-3 text-emerald-400" />
            <span>Ground Axis</span>
          </button>
        </div>

        <ErrorBoundary fallback={<div className="p-4"><TopologyFallback model={model} onSelectStation={setDrawerStation} /></div>}>
          <Canvas
            dpr={[1, 2]}
            camera={{ position: [0, 16, 22], fov: 45 }}
            style={{ height: '480px', background: 'radial-gradient(circle at 50% 35%, #08101e 0%, #05070c 75%)' }}
          >
            <StratifiedMeshScene
              model={model}
              onSelectRelay={setSelectedRelay}
              onSelectStation={setDrawerStation}
              cameraPreset={cameraPreset}
              controlsRef={controlsRef}
            />
          </Canvas>

          <div className="flex items-center justify-between px-4 py-2 border-t border-zinc-800 text-[10px] font-mono text-zinc-500 bg-zinc-950/90">
            <span>Click any relay to open inspector & manual impairment toggles · Drag to rotate · Scroll to zoom</span>
            <span className="flex items-center space-x-1.5">
              <span className="w-1.5 h-1.5 rounded-full inline-block bg-cyan-400 animate-pulse" />
              <span>Route: {model.activePath.join(' → ')}</span>
            </span>
          </div>
        </ErrorBoundary>
      </div>

      {/* Tactical Test Bench Ribbon (Drill Scenarios & Sub-300ms Reroute Convergence) */}
      <MeshTestBenchRibbon
        activePath={model.activePath}
        totalHops={model.totalHops}
        estimatedLatencyMs={model.estimatedLatencyMs}
        convergenceMs={convergenceMs}
        diversionBanner={diversionBanner}
        onScenarioTrigger={handleScenarioTrigger}
        onSimulateHop={handleSimulateHop}
        onClearDiversion={() => setDiversionBanner(null)}
        isBusy={isBusy}
      />

      {/* Anomaly Strip Integrity Telemetry */}
      <AnomalyStrip
        report={anomalyReport}
        loading={anomalyLoading}
        error={anomalyError}
        onRefresh={refreshAnomalies}
        compact
      />

      {/* Station Outbox / Inbox Message Drawer */}
      <MessageDrawer
        station={drawerStation}
        endpoints={endpoints}
        onClose={() => setDrawerStation(null)}
      />

      {/* Interactive Slide-Over Relay Inspector Drawer */}
      <RelayInspectorDrawer
        relay={selectedRelay}
        links={model.links}
        onClose={() => setSelectedRelay(null)}
        onRefresh={loadTopology}
        onNotify={setNotice}
      />
    </div>
  )
}
export default LinkTopologyView
