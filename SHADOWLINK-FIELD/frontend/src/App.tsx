import React, { useState, useEffect, useCallback } from 'react'
import { Header } from './components/Header'
import { SimulationControls } from './components/SimulationControls'
import { DualEndpointConsole } from './components/DualEndpointConsole'
import { InteroperabilityConsole } from './components/InteroperabilityConsole'
import { DiagnosticsAuditPanel } from './components/DiagnosticsAuditPanel'
import { MessageTimelineModal } from './components/MessageTimelineModal'
import { Message, QueueStats } from './types'
import { api } from './services/api'

export function App() {
  const [activeTab, setActiveTab] = useState<'console' | 'interop' | 'audit'>('console')
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean>(true)
  const [queueStats, setQueueStats] = useState<QueueStats | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [inspectedMessage, setInspectedMessage] = useState<Message | null>(null)

  const fetchData = useCallback(async () => {
    try {
      // 1. Health check
      await api.getHealth()
      setIsBackendHealthy(true)

      // 2. Queue stats & transport telemetry
      const stats = await api.getQueueStats()
      setQueueStats(stats)

      // 3. Message list
      const msgs = await api.getMessages()
      setMessages(msgs)
    } catch (err) {
      console.warn('Backend polling error (offline or starting up):', err)
      setIsBackendHealthy(false)
    }
  }, [])

  // Poll backend every 2.5 seconds
  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 2500)
    return () => clearInterval(interval)
  }, [fetchData])

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-emerald-500/30 selection:text-emerald-200">
      {/* Top Tactical Header */}
      <Header
        isBackendHealthy={isBackendHealthy}
        queueStats={queueStats}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />

      {/* Main Tactical Operational Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 space-y-6">
        {/* Virtual RF Channel Simulation Controls (always accessible to easily test severed links) */}
        <SimulationControls queueStats={queueStats} onConfigChange={fetchData} />

        {/* Tab 1: Dual Endpoint Console (Outbox & Inbox) */}
        {activeTab === 'console' && (
          <DualEndpointConsole
            messages={messages}
            isBackendHealthy={isBackendHealthy}
            onRefresh={fetchData}
            onInspectTimeline={(msg) => setInspectedMessage(msg)}
          />
        )}

        {/* Tab 2: Interoperability Gateways & Radios */}
        {activeTab === 'interop' && <InteroperabilityConsole />}

        {/* Tab 3: Diagnostics & Security Audit Logs */}
        {activeTab === 'audit' && <DiagnosticsAuditPanel />}
      </main>

      {/* Detailed Lifecycle Audit Timeline Modal */}
      <MessageTimelineModal
        message={inspectedMessage}
        onClose={() => setInspectedMessage(null)}
      />

      {/* Operational Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 px-4 py-3 text-center text-xs font-mono text-slate-600">
        SHADOWLINK FIELD Platform &bull; Offline-First Tactical Communications &bull; Radio Interoperability Layer
      </footer>
    </div>
  )
}

export default App
