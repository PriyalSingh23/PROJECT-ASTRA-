import React, { useState, useEffect, useCallback, lazy, Suspense } from 'react'
import { Header, WorkstationTab } from './components/Header'
import { TacticalTelemetryRibbon } from './components/TacticalTelemetryRibbon'
import { ViewLoader } from './components/ViewLoader'

// Eagerly loaded: the console shell and the two most-visited views, so first
// paint is instant. Everything else is code-split below.
import { MessagesView } from './components/MessagesView'
import { ConnectivityView } from './components/ConnectivityView'
import { MissionOverviewView } from './components/workstation/MissionOverviewView'

// ---------------------------------------------------------------------------
// Code-split views. Each of these becomes its own chunk, fetched on demand.
// Heavy or occasional modules (3D engine, SDR labs, modals) never block the
// initial load of the tactical console.
// ---------------------------------------------------------------------------
const TransmitterWorkbenchView = lazy(() =>
  import('./components/workstation/TransmitterWorkbenchView').then((m) => ({ default: m.TransmitterWorkbenchView })),
)
const ReceiverWorkbenchView = lazy(() =>
  import('./components/workstation/ReceiverWorkbenchView').then((m) => ({ default: m.ReceiverWorkbenchView })),
)
const LiveSignalAnalyser = lazy(() =>
  import('./components/workstation/LiveSignalAnalyser').then((m) => ({ default: m.LiveSignalAnalyser })),
)
const ChannelLabView = lazy(() =>
  import('./components/workstation/ChannelLabView').then((m) => ({ default: m.ChannelLabView })),
)
const ModelLabView = lazy(() =>
  import('./components/workstation/ModelLabView').then((m) => ({ default: m.ModelLabView })),
)
const ExperimentCentreView = lazy(() =>
  import('./components/workstation/ExperimentCentreView').then((m) => ({ default: m.ExperimentCentreView })),
)
const PipelineVisualizerView = lazy(() =>
  import('./components/workstation/PipelineVisualizerView').then((m) => ({ default: m.PipelineVisualizerView })),
)
const DiagnosticsView = lazy(() =>
  import('./components/workstation/DiagnosticsView').then((m) => ({ default: m.DiagnosticsView })),
)
const DemoModeView = lazy(() =>
  import('./components/workstation/DemoModeView').then((m) => ({ default: m.DemoModeView })),
)
const ResearchLabView = lazy(() =>
  import('./components/ResearchLabView').then((m) => ({ default: m.ResearchLabView })),
)
const LinkTopologyView = lazy(() => import('./components/topology/LinkTopologyView'))
const WaveformLabView = lazy(() =>
  import('./components/WaveformLabView').then((m) => ({ default: m.WaveformLabView })),
)

const DevicesView = lazy(() => import('./components/DevicesView').then((m) => ({ default: m.DevicesView })))
const SecurityView = lazy(() => import('./components/SecurityView').then((m) => ({ default: m.SecurityView })))
const SecurityModal = lazy(() => import('./components/SecurityModal').then((m) => ({ default: m.SecurityModal })))
const GuidedTourModal = lazy(() =>
  import('./components/guided/GuidedTourModal').then((m) => ({ default: m.GuidedTourModal })),
)
const HelpCenterModal = lazy(() =>
  import('./components/guided/HelpCenterModal').then((m) => ({ default: m.HelpCenterModal })),
)

import type { TourMode } from './components/guided/GuidedTourModal'
import { Message, QueueStats, Endpoint, User } from './types'
import { api } from './services/api'
import { outboxDb } from './services/outboxDb'
import { syncService } from './services/syncService'

export function App() {
  const [activeTab, setActiveTab] = useState<WorkstationTab>('overview')
  const [isDemoModeOpen, setIsDemoModeOpen] = useState<boolean>(false)
  const [isTourOpen, setIsTourOpen] = useState<boolean>(false)
  const [tourMode, setTourMode] = useState<TourMode>('experiment')
  const [isHelpCenterOpen, setIsHelpCenterOpen] = useState<boolean>(false)

  // Real Backend Data
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean>(true)
  const [queueStats, setQueueStats] = useState<QueueStats | null>(null)
  const [endpoints, setEndpoints] = useState<Endpoint[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [localOutboxCount, setLocalOutboxCount] = useState<number>(0)

  // User & Auth State
  const [currentUser, setCurrentUser] = useState<User | null>(null)
  const [isAuthModalOpen, setIsAuthModalOpen] = useState<boolean>(false)

  const updateOutboxCount = useCallback(async () => {
    try {
      const count = await outboxDb.countMessages()
      setLocalOutboxCount(count)
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    updateOutboxCount()
    const unsubscribe = syncService.subscribe(() => {
      updateOutboxCount()
    })
    return () => unsubscribe()
  }, [updateOutboxCount])

  // Verify active session on startup
  useEffect(() => {
    api
      .getMe()
      .then((user) => setCurrentUser(user))
      .catch(() => setCurrentUser(null))
  }, [])

  // Poll backend data
  const fetchData = useCallback(async () => {
    try {
      // 1. Health check
      await api.getHealth()
      setIsBackendHealthy(true)

      // 2. Queue stats & transport
      const stats = await api.getQueueStats()
      setQueueStats(stats)

      // 3. Endpoints
      const eps = await api.getEndpoints()
      setEndpoints(eps)

      // 4. Messages
      const msgs = await api.getMessages()
      setMessages(msgs)
    } catch (err) {
      console.warn('Backend polling error (offline or unreachable):', err)
      setIsBackendHealthy(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 2000)
    return () => clearInterval(interval)
  }, [fetchData])

  const handleLogout = async () => {
    await api.logout()
    setCurrentUser(null)
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans selection:bg-emerald-500/30 selection:text-emerald-200">
      {/* Top Professional Header */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        isBackendHealthy={isBackendHealthy}
        queueStats={queueStats}
        currentUser={currentUser}
        localOutboxCount={localOutboxCount}
        onFlushOutbox={() => syncService.flushOutbox()}
        onOpenAuth={() => setIsAuthModalOpen(true)}
        onLogout={handleLogout}
        onOpenDemo={() => setIsDemoModeOpen(true)}
        onOpenTour={(mode) => {
          setTourMode(mode)
          setIsTourOpen(true)
        }}
        onOpenHelp={() => setIsHelpCenterOpen(true)}
      />

      {/* Real-Time Tactical Telemetry Ribbon & Spectrum HUD */}
      <TacticalTelemetryRibbon isBackendHealthy={isBackendHealthy} />

      {/* Main Tactical Operational Viewport */}
      <main className="flex-1 w-full max-w-7xl mx-auto p-3 md:p-5 flex flex-col">
        <Suspense fallback={<ViewLoader label="Loading view" />}>
          {activeTab === 'overview' && (
            <MissionOverviewView
              onNavigate={(tab) => setActiveTab(tab)}
              isBackendHealthy={isBackendHealthy}
              onStartTour={(mode) => {
                setTourMode(mode)
                setIsTourOpen(true)
              }}
              onOpenHelp={() => setIsHelpCenterOpen(true)}
              onOpenDemo={() => setIsDemoModeOpen(true)}
            />
          )}

          {activeTab === 'topology' && (
            <LinkTopologyView
              endpoints={endpoints}
              messages={messages}
              queueStats={queueStats}
              isBackendHealthy={isBackendHealthy}
            />
          )}

          {activeTab === 'transmitter' && <TransmitterWorkbenchView />}

          {activeTab === 'receiver' && <ReceiverWorkbenchView />}

          {activeTab === 'analyser' && <LiveSignalAnalyser />}

          {activeTab === 'channel' && <ChannelLabView />}

          {activeTab === 'models' && <ModelLabView />}

          {activeTab === 'experiments' && <ExperimentCentreView />}

          {activeTab === 'pipeline' && <PipelineVisualizerView />}

          {activeTab === 'research' && <ResearchLabView />}

          {activeTab === 'waveform' && <WaveformLabView />}

          {activeTab === 'messages' && (
            <MessagesView
              messages={messages}
              endpoints={endpoints}
              queueStats={queueStats}
              isBackendHealthy={isBackendHealthy}
              onRefresh={fetchData}
            />
          )}

          {activeTab === 'connectivity' && (
            <ConnectivityView
              queueStats={queueStats}
              isBackendHealthy={isBackendHealthy}
              onRefresh={fetchData}
            />
          )}

          {activeTab === 'devices' && (
            <DevicesView endpoints={endpoints} onRefresh={fetchData} />
          )}

          {activeTab === 'diagnostics' && <DiagnosticsView />}

          {activeTab === 'security' && (
            <SecurityView
              currentUser={currentUser}
              onOpenAuth={() => setIsAuthModalOpen(true)}
            />
          )}
        </Suspense>
      </main>

      {/* Modals — code-split; nothing here loads until it is opened */}
      <Suspense fallback={null}>
        {/* Interactive Guided Tour & Demonstration Modal */}
        <GuidedTourModal
          isOpen={isTourOpen}
          tourMode={tourMode}
          onClose={() => setIsTourOpen(false)}
          onNavigateTab={(tab) => setActiveTab(tab)}
          onOpenHelp={() => {
            setIsTourOpen(false)
            setIsHelpCenterOpen(true)
          }}
        />

        {/* Comprehensive Help Centre & Technical Glossary Modal */}
        <HelpCenterModal
          isOpen={isHelpCenterOpen}
          onClose={() => setIsHelpCenterOpen(false)}
          onStartTour={(mode) => {
            setIsHelpCenterOpen(false)
            setTourMode(mode)
            setIsTourOpen(true)
          }}
        />

        {/* Evaluation Demonstration Mode Modal / Overlay */}
        {isDemoModeOpen && (
          <DemoModeView onExit={() => setIsDemoModeOpen(false)} />
        )}

        {/* Operator Authentication Modal */}
        <SecurityModal
          isOpen={isAuthModalOpen}
          onClose={() => setIsAuthModalOpen(false)}
          onLoginSuccess={(user) => {
            setCurrentUser(user)
            fetchData()
          }}
        />
      </Suspense>

      {/* Professional Product Footer */}
      <footer className="border-t border-zinc-900 bg-zinc-950 px-4 py-2.5 text-center text-xs font-mono text-zinc-500 flex flex-col sm:flex-row items-center justify-between max-w-7xl w-full mx-auto">
        <div className="flex items-center space-x-2">
          <span className="text-zinc-200 font-bold">ASTRA</span>
          <span>&bull;</span>
          <span>Adaptive Secure Transmission &amp; Research Architecture</span>
          <span className="px-1.5 py-0.2 rounded bg-zinc-800 text-zinc-300 text-[10px]">v4.2</span>
        </div>
        <div className="flex items-center space-x-3 mt-1 sm:mt-0 text-[11px] text-zinc-500">
          <span>AES-256-GCM v2 Authenticated</span>
          <span>&bull;</span>
          <span>RS(42,34) FEC</span>
          <span>&bull;</span>
          <span className="text-emerald-400 font-semibold">+9.03 dB LPI-CGAN Neural Modulation</span>
        </div>
      </footer>
    </div>
  )
}

export default App
