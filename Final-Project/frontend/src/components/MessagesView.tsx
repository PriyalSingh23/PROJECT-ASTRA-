import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Columns2,
  Square,
  ArrowLeftRight,
  RotateCcw,
  HardDrive,
  Radio,
  CheckCheck,
  AlertCircle,
  X,
  Layers,
  ShieldAlert,
  Sparkles,
  RefreshCw,
  WifiOff,
  Wifi,
  ShieldCheck,
} from 'lucide-react'
import { Message, InboxMessage, Endpoint, QueueStats, LocalOutboxItem } from '../types'
import { api, alphaApi, bravoApi } from '../services/api'
import { outboxDb } from '../services/outboxDb'
import { syncService } from '../services/syncService'
import { audioService } from '../services/audioService'
import { StationConsoleColumn } from './StationConsoleColumn'
import { MessageTelemetryDrawer } from './MessageTelemetryDrawer'

export interface MessagesViewProps {
  messages: Message[]
  endpoints: Endpoint[]
  queueStats: QueueStats | null
  isBackendHealthy: boolean
  onRefresh: () => void
}

export const MessagesView: React.FC<MessagesViewProps> = ({
  messages,
  endpoints,
  queueStats,
  isBackendHealthy,
  onRefresh,
}) => {
  // 1. Adaptive Viewport Modes (UI-01, D-01)
  const [viewMode, setViewMode] = useState<'single' | 'split'>('single')

  // Active sender station in Single mode
  const [activeSenderId, setActiveSenderId] = useState<string>('endpoint-a')

  // 2. Draft State Preservation Hub
  // Station Alpha state
  const [alphaComposerText, setAlphaComposerText] = useState<string>('')
  const [alphaMessageType, setAlphaMessageType] = useState<string>('STATUS_REPORT')
  const [alphaPriority, setAlphaPriority] = useState<number>(1)
  const [isAlphaSubmitting, setIsAlphaSubmitting] = useState<boolean>(false)

  // Station Bravo state
  const [bravoComposerText, setBravoComposerText] = useState<string>('')
  const [bravoMessageType, setBravoMessageType] = useState<string>('STATUS_REPORT')
  const [bravoPriority, setBravoPriority] = useState<number>(1)
  const [isBravoSubmitting, setIsBravoSubmitting] = useState<boolean>(false)

  // Selected message for slide-out telemetry drawer (UI-03, D-03)
  const [selectedMessage, setSelectedMessage] = useState<Message | null>(null)

  // 3. Live Recipient Inbox Verification (UI-02, D-02) & Multi-Daemon Topology (Phase 6)
  const [inboxA, setInboxA] = useState<InboxMessage[]>([])
  const [inboxB, setInboxB] = useState<InboxMessage[]>([])
  const [isAlphaDaemonOnline, setIsAlphaDaemonOnline] = useState<boolean>(true)
  const [isBravoDaemonOnline, setIsBravoDaemonOnline] = useState<boolean>(true)
  const [alphaMessagesList, setAlphaMessagesList] = useState<Message[]>([])
  const [bravoMessagesList, setBravoMessagesList] = useState<Message[]>([])

  // Local outbox (IndexedDB offline store)
  const [localOutbox, setLocalOutbox] = useState<LocalOutboxItem[]>([])
  const [isStorageNearCeiling, setIsStorageNearCeiling] = useState<boolean>(false)
  const [duplicateHighlightId, setDuplicateHighlightId] = useState<string | null>(null)
  const [submitNotice, setSubmitNotice] = useState<string | null>(null)
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false)
  const [isFlushingOutbox, setIsFlushingOutbox] = useState<boolean>(false)

  const isLinkOnline = isBackendHealthy && (queueStats?.transport?.is_online ?? true)
  const isChannelImpaired =
    queueStats?.transport &&
    ((queueStats.transport.drop_rate || 0) > 0 || (queueStats.transport.latency_ms || 0) > 0)

  // Station names
  const alphaName = useMemo(() => {
    return endpoints.find((ep) => ep.endpoint_id === 'endpoint-a')?.display_name || 'Station Alpha'
  }, [endpoints])

  const bravoName = useMemo(() => {
    return endpoints.find((ep) => ep.endpoint_id === 'endpoint-b')?.display_name || 'Station Bravo'
  }, [endpoints])

  // Instant Station Swap
  const handleSwapStations = () => {
    setActiveSenderId((prev) => (prev === 'endpoint-a' ? 'endpoint-b' : 'endpoint-a'))
  }

  // Decoupled Polling Queries for Station Alpha and Station Bravo daemons (D-02)
  const refreshAlpha = useCallback(async () => {
    try {
      const [inboxItems, msgs] = await Promise.all([
        alphaApi.getInbox('endpoint-a'),
        alphaApi.getMessages({ sender: 'endpoint-a' }),
      ])
      setInboxA(inboxItems)
      setAlphaMessagesList(msgs)
      setIsAlphaDaemonOnline(true)
    } catch (err) {
      console.warn('Could not refresh Station Alpha daemon (:5051):', err)
      setIsAlphaDaemonOnline(false)
    }
  }, [])

  const refreshBravo = useCallback(async () => {
    try {
      const [inboxItems, msgs] = await Promise.all([
        bravoApi.getInbox('endpoint-b'),
        bravoApi.getMessages({ sender: 'endpoint-b' }),
      ])
      setInboxB(inboxItems)
      setBravoMessagesList(msgs)
      setIsBravoDaemonOnline(true)
    } catch (err) {
      console.warn('Could not refresh Station Bravo daemon (:5052):', err)
      setIsBravoDaemonOnline(false)
    }
  }, [])

  const refreshInboxes = useCallback(() => {
    refreshAlpha()
    refreshBravo()
  }, [refreshAlpha, refreshBravo])

  const refreshLocalOutbox = useCallback(async () => {
    try {
      const items = await outboxDb.getAllMessages()
      setLocalOutbox(items)
      const nearCeiling = await outboxDb.isNearCeiling()
      setIsStorageNearCeiling(nearCeiling)
    } catch (e) {
      console.warn('Could not read IndexedDB outbox:', e)
    }
  }, [])

  // Initial fetch for inboxes and local outbox
  useEffect(() => {
    refreshInboxes()
    refreshLocalOutbox()
  }, [refreshInboxes, refreshLocalOutbox])

  // Subscribe to syncService multi-tab BroadcastChannel & Web Lock updates
  useEffect(() => {
    const unsubscribe = syncService.subscribe(() => {
      refreshLocalOutbox()
      refreshInboxes()
      onRefresh()
    })
    return () => unsubscribe()
  }, [refreshLocalOutbox, refreshInboxes, onRefresh])

  // 5. High-Performance 1.5s Adaptive Polling with Background Tab Throttling (D-04)
  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval> | null = null

    const startPolling = (intervalMs: number) => {
      if (intervalId) clearInterval(intervalId)
      intervalId = setInterval(() => {
        refreshInboxes()
        refreshLocalOutbox()
        onRefresh()
      }, intervalMs)
    }

    startPolling(1500)

    const handleVisibilityChange = () => {
      if (document.hidden) {
        startPolling(5000)
      } else {
        refreshInboxes()
        refreshLocalOutbox()
        onRefresh()
        startPolling(1500)
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      if (intervalId) clearInterval(intervalId)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [refreshInboxes, refreshLocalOutbox, onRefresh])

  // Unified lookup map of durable inbox records across both stations
  const allInboxMap = useMemo(() => {
    const map = new Map<string, InboxMessage>()
    inboxA.forEach((item) => map.set(item.message_id, item))
    inboxB.forEach((item) => map.set(item.message_id, item))
    return map
  }, [inboxA, inboxB])

  // Outbox collections
  const alphaOutbox = useMemo(
    () => (alphaMessagesList.length > 0 ? alphaMessagesList : messages.filter((m) => m.sender_endpoint_id === 'endpoint-a')),
    [alphaMessagesList, messages]
  )

  const bravoOutbox = useMemo(
    () => (bravoMessagesList.length > 0 ? bravoMessagesList : messages.filter((m) => m.sender_endpoint_id === 'endpoint-b')),
    [bravoMessagesList, messages]
  )

  // Auto-flush pending IndexedDB outbox via Web Locks when link is healthy
  useEffect(() => {
    if (!isBackendHealthy || !isLinkOnline || localOutbox.length === 0) return
    syncService.flushOutbox()
  }, [isBackendHealthy, isLinkOnline, localOutbox.length])

  const handleManualFlush = async () => {
    setIsFlushingOutbox(true)
    try {
      const res = await syncService.flushOutbox()
      if (res.flushed > 0 || res.duplicates > 0) {
        setSubmitNotice(
          `Local outbox flushed: ${res.flushed} transmitted, ${res.duplicates} deduplicated, ${res.failed} failed.`
        )
      }
      await refreshLocalOutbox()
      refreshInboxes()
      onRefresh()
    } finally {
      setIsFlushingOutbox(false)
    }
  }

  const handleRestoreCleanLink = async () => {
    try {
      await api.updateSimTransport({ reset: true, preset: 'NOMINAL' })
      audioService.playRestoreChime()
      setSubmitNotice('Virtual RF Channel restored to NOMINAL (0ms, 0% loss).')
      onRefresh()
    } catch (err: any) {
      setSubmitNotice(`Link restore error: ${err.message || err}`)
    }
  }

  // Generic message submission handler
  const submitStationMessage = async (
    senderId: string,
    recipientId: string,
    payloadText: string,
    msgType: string,
    prio: number,
    ttl: number
  ) => {
    if (!payloadText.trim()) return

    const idempotencyKey = `msg-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
    const payload = payloadText.trim()
    const targetApi = senderId === 'endpoint-a' ? alphaApi : bravoApi
    const isDaemonOnline = senderId === 'endpoint-a' ? isAlphaDaemonOnline : isBravoDaemonOnline
    const stationLabel = senderId === 'endpoint-a' ? 'Alpha (:5051)' : 'Bravo (:5052)'

    // If backend, virtual link, or station daemon is offline, store in browser IndexedDB outbox
    if (!isBackendHealthy || !isLinkOnline || !isDaemonOnline) {
      try {
        await outboxDb.saveMessage({
          client_idempotency_key: idempotencyKey,
          sender_endpoint_id: senderId,
          recipient_endpoint_id: recipientId,
          payload,
          message_type: msgType,
          priority: prio,
          expires_in_seconds: ttl,
          created_at: new Date().toISOString(),
          sync_status: 'PENDING_LOCAL',
        })
        await refreshLocalOutbox()
        syncService.broadcastMutation()
        setSubmitNotice(`Saved to browser IndexedDB outbox (${stationLabel} daemon offline, will sync on reconnect)`)
      } catch (err: unknown) {
        const errorMsg = err instanceof Error ? err.message : String(err)
        setSubmitNotice(`Local outbox error: ${errorMsg}`)
      }
      return
    }

    // Station daemon is online: submit directly via dedicated station REST API
    try {
      const newMsg = await targetApi.submitMessage({
        client_idempotency_key: idempotencyKey,
        sender_endpoint_id: senderId,
        recipient_endpoint_id: recipientId,
        payload,
        message_type: msgType,
        priority: prio,
        expires_in_seconds: ttl,
      })

      // Idempotent duplicate match feedback (D-09)
      if (newMsg && newMsg.is_new === false) {
        setSubmitNotice('Deduplicated: Existing canonical message record returned. No duplicate enqueued.')
        setDuplicateHighlightId(newMsg.message_id)
        setSelectedMessage(newMsg)
        setTimeout(() => setDuplicateHighlightId(null), 3000)
      } else {
        setSelectedMessage(newMsg)
      }

      onRefresh()
      refreshInboxes()
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : String(err)
      setSubmitNotice(`Send failed: ${errorMsg}`)
      try {
        await outboxDb.saveMessage({
          client_idempotency_key: idempotencyKey,
          sender_endpoint_id: senderId,
          recipient_endpoint_id: recipientId,
          payload,
          message_type: msgType,
          priority: prio,
          expires_in_seconds: ttl,
          created_at: new Date().toISOString(),
          sync_status: 'PENDING_LOCAL',
          error_message: errorMsg,
        })
        await refreshLocalOutbox()
        syncService.broadcastMutation()
      } catch {
        // ignore
      }
    }
  }

  // Handle message submission from Station Alpha
  const handleSendAlphaMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!alphaComposerText.trim() || isAlphaSubmitting) return

    setIsAlphaSubmitting(true)
    setSubmitNotice(null)
    try {
      await submitStationMessage(
        'endpoint-a',
        'endpoint-b',
        alphaComposerText,
        alphaMessageType,
        alphaPriority,
        86400
      )
      setAlphaComposerText('')
    } finally {
      setIsAlphaSubmitting(false)
    }
  }

  // Handle message submission from Station Bravo
  const handleSendBravoMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!bravoComposerText.trim() || isBravoSubmitting) return

    setIsBravoSubmitting(true)
    setSubmitNotice(null)
    try {
      await submitStationMessage(
        'endpoint-b',
        'endpoint-a',
        bravoComposerText,
        bravoMessageType,
        bravoPriority,
        86400
      )
      setBravoComposerText('')
    } finally {
      setIsBravoSubmitting(false)
    }
  }

  // Manual refresh trigger
  const handleManualRefresh = async () => {
    setIsRefreshing(true)
    try {
      refreshInboxes()
      refreshLocalOutbox()
      onRefresh()
    } finally {
      setTimeout(() => setIsRefreshing(false), 500)
    }
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-white dark:bg-[#0B0F17] border border-slate-200 dark:border-zinc-800 rounded-xl max-w-7xl w-full mx-auto shadow-xl h-[calc(100vh-8.5rem)] relative">
      {/* Storage Ceiling Alert Banner (D-21) */}
      {isStorageNearCeiling && (
        <div className="px-4 py-2 bg-amber-50 dark:bg-amber-950/90 border-b border-amber-300 dark:border-amber-600/70 text-xs font-mono text-amber-900 dark:text-amber-200 flex items-center justify-between shrink-0 shadow-lg animate-pulse">
          <div className="flex items-center space-x-2">
            <ShieldAlert className="w-4 h-4 text-amber-500 dark:text-amber-400 shrink-0" />
            <span>
              <strong>⚠️ LOCAL OUTBOX NEAR CEILING:</strong> {localOutbox.length}/500 items stored in IndexedDB.
              Flush outbox to prevent message discard.
            </span>
          </div>
          <button
            type="button"
            onClick={handleManualFlush}
            disabled={isFlushingOutbox}
            className="px-2.5 py-1 rounded bg-amber-600 hover:bg-amber-500 text-white font-mono text-[10px] font-bold shadow transition-colors cursor-pointer"
          >
            {isFlushingOutbox ? 'Flushing...' : 'Flush Outbox Now'}
          </button>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TACTICAL CONSOLE TOOLBAR & 3D VIEWPORT TOGGLE                              */}
      {/* ========================================================================= */}
      <div className="px-4 py-2.5 bg-slate-50 dark:bg-[#131B2E] border-b border-slate-200 dark:border-zinc-800 flex items-center justify-between flex-wrap gap-2.5 shrink-0">
        {/* Left: Operator Station Selector (Single Viewport) & Swap Identity */}
        <div className="flex items-center space-x-2">
          {viewMode === 'single' ? (
            <>
              <span className="text-[10px] font-mono uppercase text-slate-600 dark:text-zinc-400 font-bold tracking-wider">
                Operator Station:
              </span>
              <div className="inline-flex rounded-lg bg-slate-100 dark:bg-[#0B0F17] p-1 border border-slate-300 dark:border-zinc-800 text-xs font-mono shadow-inner">
                <button
                  type="button"
                  onClick={() => setActiveSenderId('endpoint-a')}
                  className={`px-3 py-1 rounded-md transition-all font-semibold flex items-center space-x-1.5 cursor-pointer ${
                    activeSenderId === 'endpoint-a'
                      ? 'bg-cyan-600 text-white shadow-sm'
                      : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-200'
                  }`}
                >
                  <Radio className="w-3.5 h-3.5" />
                  <span>Alpha</span>
                  <span className="text-[9px] opacity-75">(endpoint-a)</span>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveSenderId('endpoint-b')}
                  className={`px-3 py-1 rounded-md transition-all font-semibold flex items-center space-x-1.5 cursor-pointer ${
                    activeSenderId === 'endpoint-b'
                      ? 'bg-emerald-600 text-white shadow-sm'
                      : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-200'
                  }`}
                >
                  <Radio className="w-3.5 h-3.5" />
                  <span>Bravo</span>
                  <span className="text-[9px] opacity-75">(endpoint-b)</span>
                </button>
              </div>

              <button
                type="button"
                onClick={handleSwapStations}
                title="Instant Station Identity Swap (⇄)"
                className="p-1.5 rounded-lg bg-slate-100 dark:bg-[#0B0F17] border border-slate-300 dark:border-zinc-800 text-slate-700 dark:text-zinc-300 hover:text-cyan-600 dark:hover:text-cyan-400 hover:border-cyan-500/50 transition-all flex items-center space-x-1.5 text-xs font-mono shadow-xs active:translate-y-0.5 cursor-pointer"
              >
                <ArrowLeftRight className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />
                <span className="hidden sm:inline">Swap Identity</span>
              </button>
            </>
          ) : (
            <div className="flex items-center space-x-2 text-xs font-mono">
              <span className="px-2.5 py-1 rounded bg-cyan-100 text-cyan-900 border border-cyan-300 dark:bg-[#0B0F17] dark:border-cyan-500/40 dark:text-cyan-300 font-bold flex items-center space-x-1.5">
                <span className="w-2 h-2 rounded-full bg-cyan-500 dark:bg-cyan-400 animate-pulse" />
                <span>Station Alpha</span>
              </span>
              <span className="text-slate-400 dark:text-zinc-500 font-bold">&harr;</span>
              <span className="px-2.5 py-1 rounded bg-emerald-100 text-emerald-900 border border-emerald-300 dark:bg-[#0B0F17] dark:border-emerald-500/40 dark:text-emerald-300 font-bold flex items-center space-x-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500 dark:bg-emerald-400 animate-pulse" />
                <span>Station Bravo</span>
              </span>
            </div>
          )}

          {/* Link Impairment Banner Indicator with Restore Action (D-02, D-04) */}
          {(!isLinkOnline || isChannelImpaired) && (
            <div className="flex items-center space-x-1.5 ml-2">
              <span
                className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border flex items-center space-x-1 ${
                  !isLinkOnline
                    ? 'bg-rose-950/80 border-rose-600/70 text-rose-300'
                    : 'bg-amber-950/80 border-amber-500/60 text-amber-300'
                }`}
              >
                {!isLinkOnline ? (
                  <>
                    <WifiOff className="w-3 h-3 text-rose-400" />
                    <span>LINK SEVERED</span>
                  </>
                ) : (
                  <>
                    <Wifi className="w-3 h-3 text-amber-400 animate-pulse" />
                    <span>
                      IMPAIRED ({Math.round((queueStats?.transport?.drop_rate || 0) * 100)}% DROP)
                    </span>
                  </>
                )}
              </span>

              <button
                type="button"
                onClick={handleRestoreCleanLink}
                className="px-2 py-0.5 rounded bg-emerald-900/60 hover:bg-emerald-800 border border-emerald-500/50 text-emerald-300 font-mono text-[10px] font-bold shadow transition-all cursor-pointer flex items-center space-x-1"
                title="Restore nominal virtual RF link conditions (0ms latency, 0% drop)"
              >
                <Sparkles className="w-2.5 h-2.5 text-emerald-400" />
                <span>Restore Clean Link</span>
              </button>
            </div>
          )}
        </div>

        {/* Center: 3D Tactical Viewport Toggle (Single Console vs Dual Split-Screen) */}
        <div className="flex items-center space-x-1 bg-slate-100 dark:bg-[#0B0F17] p-1 rounded-lg border border-slate-300 dark:border-zinc-800 text-xs font-mono shadow-inner">
          <button
            type="button"
            onClick={() => setViewMode('single')}
            className={`px-3 py-1 rounded-md flex items-center space-x-1.5 transition-all cursor-pointer ${
              viewMode === 'single'
                ? 'bg-white text-emerald-800 dark:bg-zinc-800 dark:text-emerald-400 font-bold border border-emerald-400 dark:border-emerald-500/50 shadow-xs'
                : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-200'
            }`}
          >
            <Square className="w-3.5 h-3.5" />
            <span>Single Console</span>
          </button>
          <button
            type="button"
            onClick={() => setViewMode('split')}
            className={`px-3 py-1 rounded-md flex items-center space-x-1.5 transition-all cursor-pointer ${
              viewMode === 'split'
                ? 'bg-white text-cyan-800 dark:bg-zinc-800 dark:text-cyan-400 font-bold border border-cyan-400 dark:border-cyan-500/50 shadow-xs'
                : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-200'
            }`}
          >
            <Columns2 className="w-3.5 h-3.5" />
            <span>Dual Split-Screen</span>
          </button>
        </div>

        {/* Right: Live Recipient Inboxes & Telemetry Summary */}
        <div className="flex items-center space-x-2 text-[10px] font-mono">
          {queueStats && queueStats.active_leases > 0 && (
            <span className="hidden md:flex items-center space-x-1 px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-950/70 border border-blue-300 dark:border-blue-500/40 text-blue-900 dark:text-blue-300">
              <Layers className="w-3 h-3 text-blue-500 dark:text-blue-400" />
              <span>Leases: {queueStats.active_leases}</span>
            </span>
          )}

          <span className="px-2 py-0.5 rounded bg-cyan-100 dark:bg-cyan-950/40 border border-cyan-300 dark:border-cyan-500/40 text-cyan-900 dark:text-cyan-300 flex items-center space-x-1 font-mono text-[10px] shadow-xs">
            <ShieldCheck className="w-3 h-3 text-cyan-600 dark:text-cyan-400" />
            <span>PQC HYBRID: ML-KEM-768</span>
          </span>

          <span className="px-2 py-0.5 rounded bg-white dark:bg-[#0B0F17] border border-cyan-300 dark:border-cyan-500/40 text-cyan-900 dark:text-cyan-300 flex items-center space-x-1 shadow-xs">
            <CheckCheck className="w-3 h-3 text-cyan-600 dark:text-cyan-400" />
            <span>
              Alpha Inbox: <strong className="font-bold">{inboxA.length}</strong>
            </span>
          </span>

          <span className="px-2 py-0.5 rounded bg-white dark:bg-[#0B0F17] border border-emerald-300 dark:border-emerald-500/40 text-emerald-900 dark:text-emerald-300 flex items-center space-x-1 shadow-xs">
            <CheckCheck className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
            <span>
              Bravo Inbox: <strong className="font-bold">{inboxB.length}</strong>
            </span>
          </span>

          {localOutbox.length > 0 && (
            <div className="flex items-center space-x-1">
              <span className="px-2 py-0.5 rounded bg-amber-950/70 border border-amber-500/50 text-amber-300 flex items-center space-x-1 animate-pulse">
                <HardDrive className="w-3 h-3 text-amber-400" />
                <span>Offline Queue: {localOutbox.length}</span>
              </span>
              <button
                type="button"
                onClick={handleManualFlush}
                disabled={isFlushingOutbox}
                title="Flush local offline messages to backend via Web Locks"
                className="px-2 py-0.5 rounded bg-amber-600 hover:bg-amber-500 text-white font-mono text-[10px] font-bold shadow flex items-center space-x-1 cursor-pointer transition-all"
              >
                <RefreshCw className={`w-2.5 h-2.5 ${isFlushingOutbox ? 'animate-spin' : ''}`} />
                <span>Flush</span>
              </button>
            </div>
          )}

          <button
            type="button"
            onClick={handleManualRefresh}
            title="Refresh Inboxes & Telemetry"
            className="p-1 rounded bg-[#0B0F17] border border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700 transition-all cursor-pointer"
          >
            <RotateCcw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-cyan-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Notice Banner */}
      {submitNotice && (
        <div className="px-4 py-1.5 bg-cyan-950/80 border-b border-cyan-800/60 text-xs font-mono text-cyan-200 flex items-center justify-between shrink-0 shadow-md">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
            <span>{submitNotice}</span>
          </div>
          <button
            type="button"
            onClick={() => setSubmitNotice(null)}
            className="text-cyan-400 hover:text-cyan-200 p-0.5 cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MAIN WORKSPACE: SINGLE OR DUAL SPLIT-SCREEN                                */}
      {/* ========================================================================= */}
      <div className="flex-1 overflow-hidden p-3 min-h-0">
        {viewMode === 'split' ? (
          /* Dual Split-Screen Mode: Side-by-Side Station Columns */
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 h-full overflow-hidden">
            <StationConsoleColumn
              stationId="endpoint-a"
              stationName={alphaName}
              targetStationId="endpoint-b"
              targetStationName={bravoName}
              outboxMessages={alphaOutbox}
              inboxMessages={inboxA}
              allInboxMap={allInboxMap}
              selectedMessage={selectedMessage}
              onSelectMessage={setSelectedMessage}
              composerText={alphaComposerText}
              onComposerTextChange={setAlphaComposerText}
              messageType={alphaMessageType}
              onMessageTypeChange={setAlphaMessageType}
              priority={alphaPriority}
              onPriorityChange={setAlphaPriority}
              isSubmitting={isAlphaSubmitting}
              onSubmit={handleSendAlphaMessage}
              isSplitMode={true}
              localOutboxItems={localOutbox}
              isLinkOnline={isLinkOnline}
              duplicateHighlightId={duplicateHighlightId}
              onFlushOutbox={handleManualFlush}
              stationPort={5051}
              dbPath="alpha.db"
              isDaemonOnline={isAlphaDaemonOnline}
            />

            <StationConsoleColumn
              stationId="endpoint-b"
              stationName={bravoName}
              targetStationId="endpoint-a"
              targetStationName={alphaName}
              outboxMessages={bravoOutbox}
              inboxMessages={inboxB}
              allInboxMap={allInboxMap}
              selectedMessage={selectedMessage}
              onSelectMessage={setSelectedMessage}
              composerText={bravoComposerText}
              onComposerTextChange={setBravoComposerText}
              messageType={bravoMessageType}
              onMessageTypeChange={setBravoMessageType}
              priority={bravoPriority}
              onPriorityChange={setBravoPriority}
              isSubmitting={isBravoSubmitting}
              onSubmit={handleSendBravoMessage}
              isSplitMode={true}
              localOutboxItems={localOutbox}
              isLinkOnline={isLinkOnline}
              duplicateHighlightId={duplicateHighlightId}
              onFlushOutbox={handleManualFlush}
              stationPort={5052}
              dbPath="bravo.db"
              isDaemonOnline={isBravoDaemonOnline}
            />
          </div>
        ) : (
          /* Single Console Mode: Focused Station Column */
          <div className="h-full max-w-4xl mx-auto overflow-hidden">
            {activeSenderId === 'endpoint-a' ? (
              <StationConsoleColumn
                stationId="endpoint-a"
                stationName={alphaName}
                targetStationId="endpoint-b"
                targetStationName={bravoName}
                outboxMessages={alphaOutbox}
                inboxMessages={inboxA}
                allInboxMap={allInboxMap}
                selectedMessage={selectedMessage}
                onSelectMessage={setSelectedMessage}
                composerText={alphaComposerText}
                onComposerTextChange={setAlphaComposerText}
                messageType={alphaMessageType}
                onMessageTypeChange={setAlphaMessageType}
                priority={alphaPriority}
                onPriorityChange={setAlphaPriority}
                isSubmitting={isAlphaSubmitting}
                onSubmit={handleSendAlphaMessage}
                isSplitMode={false}
                localOutboxItems={localOutbox}
                isLinkOnline={isLinkOnline}
                duplicateHighlightId={duplicateHighlightId}
                onFlushOutbox={handleManualFlush}
                stationPort={5051}
                dbPath="alpha.db"
                isDaemonOnline={isAlphaDaemonOnline}
              />
            ) : (
              <StationConsoleColumn
                stationId="endpoint-b"
                stationName={bravoName}
                targetStationId="endpoint-a"
                targetStationName={alphaName}
                outboxMessages={bravoOutbox}
                inboxMessages={inboxB}
                allInboxMap={allInboxMap}
                selectedMessage={selectedMessage}
                onSelectMessage={setSelectedMessage}
                composerText={bravoComposerText}
                onComposerTextChange={setBravoComposerText}
                messageType={bravoMessageType}
                onMessageTypeChange={setBravoMessageType}
                priority={bravoPriority}
                onPriorityChange={setBravoPriority}
                isSubmitting={isBravoSubmitting}
                onSubmit={handleSendBravoMessage}
                isSplitMode={false}
                localOutboxItems={localOutbox}
                isLinkOnline={isLinkOnline}
                duplicateHighlightId={duplicateHighlightId}
                onFlushOutbox={handleManualFlush}
                stationPort={5052}
                dbPath="bravo.db"
                isDaemonOnline={isBravoDaemonOnline}
              />
            )}
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* SLIDE-OUT TACTICAL TELEMETRY DRAWER (UI-03, D-03)                          */}
      {/* ========================================================================= */}
      <MessageTelemetryDrawer
        isOpen={!!selectedMessage}
        onClose={() => setSelectedMessage(null)}
        message={selectedMessage}
        inboxRecord={selectedMessage ? allInboxMap.get(selectedMessage.message_id) : null}
      />
    </div>
  )
}
