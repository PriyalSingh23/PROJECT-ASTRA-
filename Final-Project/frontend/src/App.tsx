import React, { useState, useEffect, useCallback, lazy, Suspense } from 'react'
import { AstraSidebar, AstraTab } from './components/AstraSidebar'
import { AstraTopBar } from './components/AstraTopBar'
import { AstraOverview } from './components/AstraOverview'
import { AstraSpectrumWaterfallLab } from './components/AstraSpectrumWaterfallLab'
import { AstraSettingsView } from './components/AstraSettingsView'
import { ViewLoader } from './components/ViewLoader'

// Eagerly loaded views
import { MessagesView } from './components/MessagesView'

// Lazy-loaded subviews
const LinkTopologyView = lazy(() => import('./components/topology/LinkTopologyView'))
const WaveformLabView = lazy(() =>
  import('./components/WaveformLabView').then((m) => ({ default: m.WaveformLabView })),
)
const ResearchLabView = lazy(() =>
  import('./components/ResearchLabView').then((m) => ({ default: m.ResearchLabView })),
)
const DevicesView = lazy(() =>
  import('./components/DevicesView').then((m) => ({ default: m.DevicesView })),
)

import { Message, QueueStats, Endpoint, User } from './types'
import { api } from './services/api'
import { outboxDb } from './services/outboxDb'
import { syncService } from './services/syncService'

export function App() {
  const [activeTab, setActiveTab] = useState<AstraTab>('overview')
  const [isNightMode, setIsNightMode] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem('astra_theme')
      if (saved) return saved === 'dark'
      return false
    } catch {
      return false
    }
  })

  // Synchronize Night Mode with html data-theme and class
  useEffect(() => {
    if (isNightMode) {
      document.documentElement.setAttribute('data-theme', 'dark')
      document.documentElement.classList.add('dark')
      try {
        localStorage.setItem('astra_theme', 'dark')
      } catch {}
    } else {
      document.documentElement.setAttribute('data-theme', 'light')
      document.documentElement.classList.remove('dark')
      try {
        localStorage.setItem('astra_theme', 'light')
      } catch {}
    }
  }, [isNightMode])

  // Backend state
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean>(true)
  const [queueStats, setQueueStats] = useState<QueueStats | null>(null)
  const [endpoints, setEndpoints] = useState<Endpoint[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [localOutboxCount, setLocalOutboxCount] = useState<number>(0)
  const [currentUser, setCurrentUser] = useState<User | null>(null)

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

  useEffect(() => {
    api
      .getMe()
      .then((user) => setCurrentUser(user))
      .catch(() => setCurrentUser(null))
  }, [])

  const fetchData = useCallback(async () => {
    try {
      await api.getHealth()
      setIsBackendHealthy(true)

      const stats = await api.getQueueStats()
      setQueueStats(stats)

      const eps = await api.getEndpoints()
      setEndpoints(eps)

      const msgs = await api.getMessages()
      setMessages(msgs)
    } catch (err) {
      console.warn('Backend polling error (offline or unreachable):', err)
      setIsBackendHealthy(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 3000)
    return () => clearInterval(interval)
  }, [fetchData])

  return (
    <div className="app-shell flex min-h-screen bg-[var(--bg)] text-[var(--ink)]">
      {/* Left Neomorphic Collapsible Sidebar */}
      <AstraSidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        isNightMode={isNightMode}
        setIsNightMode={setIsNightMode}
        isBackendHealthy={isBackendHealthy}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <AstraTopBar
          activeTab={activeTab}
          isNightMode={isNightMode}
          setIsNightMode={setIsNightMode}
          isBackendHealthy={isBackendHealthy}
        />

        <main className="flex-1 p-4 md:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          <Suspense fallback={<ViewLoader label="Loading ASTRA Workspace" />}>
            {activeTab === 'overview' && (
              <AstraOverview
                setActiveTab={setActiveTab}
                isBackendHealthy={isBackendHealthy}
              />
            )}

            {activeTab === 'spectrum' && <AstraSpectrumWaterfallLab />}

            {activeTab === 'waveform' && <WaveformLabView />}

            {activeTab === 'topology' && (
              <LinkTopologyView
                endpoints={endpoints}
                messages={messages}
                queueStats={queueStats}
                isBackendHealthy={isBackendHealthy}
              />
            )}

            {activeTab === 'messages' && (
              <MessagesView
                messages={messages}
                endpoints={endpoints}
                queueStats={queueStats}
                isBackendHealthy={isBackendHealthy}
                onRefresh={fetchData}
              />
            )}

            {activeTab === 'research' && <ResearchLabView />}

            {activeTab === 'hardware' && (
              <DevicesView endpoints={endpoints} onRefresh={fetchData} />
            )}

            {activeTab === 'settings' && (
              <AstraSettingsView
                isNightMode={isNightMode}
                setIsNightMode={setIsNightMode}
              />
            )}
          </Suspense>
        </main>
      </div>
    </div>
  )
}

export default App
