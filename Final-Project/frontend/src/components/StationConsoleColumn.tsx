import React, { useState, useMemo, useRef, useEffect } from 'react'
import {
  Send,
  Radio,
  CheckCheck,
  Clock,
  RotateCcw,
  ArrowRight,
  Activity,
  Key,
  HardDrive,
  RefreshCw,
  ShieldCheck,
  AlertTriangle,
} from 'lucide-react'
import { Message, InboxMessage, LocalOutboxItem } from '../types'
import { InboxReceiptCard } from './InboxReceiptCard'
import { formatMicroseconds } from './MessageTelemetryDrawer'
import { api } from '../services/api'
import { syncService } from '../services/syncService'

export interface StationConsoleColumnProps {
  stationId: string
  stationName: string
  targetStationId: string
  targetStationName: string
  outboxMessages: Message[]
  inboxMessages: InboxMessage[]
  allInboxMap: Map<string, InboxMessage>
  selectedMessage: Message | null
  onSelectMessage: (msg: Message) => void
  composerText: string
  onComposerTextChange: (text: string) => void
  messageType: string
  onMessageTypeChange: (type: string) => void
  priority: number
  onPriorityChange: (priority: number) => void
  isSubmitting: boolean
  onSubmit: (e?: React.FormEvent) => void
  isSplitMode: boolean
  localOutboxItems?: LocalOutboxItem[]
  isLinkOnline: boolean
  duplicateHighlightId?: string | null
  onFlushOutbox?: () => void
  stationPort?: number
  dbPath?: string
  isDaemonOnline?: boolean
}

type FeedFilter = 'all' | 'outbox' | 'inbox'

interface FeedEntry {
  id: string
  kind: 'outbox' | 'inbox' | 'local_outbox'
  timestamp: number
  outboxMsg?: Message
  inboxMsg?: InboxMessage
  localOutboxItem?: LocalOutboxItem
}

const RetryCountdownBadge: React.FC<{
  nextRetryAt: string | null
  retryCount: number
  maxRetries: number
}> = ({ nextRetryAt, retryCount, maxRetries }) => {
  const [secondsLeft, setSecondsLeft] = useState<string>('—')

  useEffect(() => {
    if (!nextRetryAt) {
      setSecondsLeft('0.0')
      return
    }

    const update = () => {
      const target = new Date(nextRetryAt).getTime()
      const now = Date.now()
      const diff = Math.max(0, (target - now) / 1000)
      setSecondsLeft(diff.toFixed(1))
    }

    update()
    const interval = setInterval(update, 100)
    return () => clearInterval(interval)
  }, [nextRetryAt])

  return (
    <span className="bg-amber-950/80 border border-amber-500/60 text-amber-300 font-mono text-[9px] font-bold px-2 py-0.5 rounded flex items-center space-x-1 animate-pulse">
      <Clock className="w-2.5 h-2.5 text-amber-400" />
      <span>
        Attempt {retryCount + 1}/{maxRetries || 5} • Next in {secondsLeft}s [Backoff + Jitter]
      </span>
    </span>
  )
}

export const StationConsoleColumn: React.FC<StationConsoleColumnProps> = ({
  stationId,
  stationName,
  targetStationId,
  targetStationName,
  outboxMessages,
  inboxMessages,
  allInboxMap,
  selectedMessage,
  onSelectMessage,
  composerText,
  onComposerTextChange,
  messageType,
  onMessageTypeChange,
  priority,
  onPriorityChange,
  isSubmitting,
  onSubmit,
  isSplitMode,
  localOutboxItems = [],
  isLinkOnline,
  duplicateHighlightId,
  onFlushOutbox,
  stationPort,
  dbPath,
  isDaemonOnline = true,
}) => {
  const [activeFilter, setActiveFilter] = useState<FeedFilter>('all')
  const feedEndRef = useRef<HTMLDivElement>(null)

  const isStationAlpha = stationId === 'endpoint-a'
  const stationAccent = isStationAlpha ? '#06B6D4' : '#10B981'
  const stationBorderColor = isStationAlpha ? 'border-cyan-500/40' : 'border-emerald-500/40'
  const stationBadgeBg = isStationAlpha
    ? 'bg-cyan-950/70 border-cyan-500/50 text-cyan-300'
    : 'bg-emerald-950/70 border-emerald-500/50 text-emerald-300'
  const stationGlow = isStationAlpha
    ? 'shadow-[0_0_15px_rgba(6,182,212,0.15)]'
    : 'shadow-[0_0_15px_rgba(16,185,129,0.15)]'

  // Real-time Tactical RF Frame & Physical Layer Budget (PQC Envelope v3, Task 07-02-03)
  const rfMetrics = useMemo(() => {
    const rawBytes = new TextEncoder().encode(composerText).length
    const envelopeBytes = rawBytes > 0 ? rawBytes + 1150 : 0 // 1150B PQC Hybrid Encapsulation Overhead (D-05, D-07)
    const rsChunks = Math.max(1, Math.ceil((envelopeBytes || 1) / 34))
    const totalRsCodewordBytes = rsChunks * 42 // RS(42,34)
    const totalBasebandSamples = rsChunks * 576 // 64 ZC + 512 Waveform Synthesis
    const burstAirtimeMs = ((totalBasebandSamples / 245760) * 1000).toFixed(2)
    const dmrChunks = Math.max(1, Math.ceil(envelopeBytes / 276))
    const dmrWireBudget = dmrChunks * 280
    return {
      rawBytes,
      envelopeBytes,
      gcmEnvelopeBytes: envelopeBytes,
      rsChunks,
      totalRsCodewordBytes,
      burstAirtimeMs,
      dmrChunks,
      dmrWireBudget,
    }
  }, [composerText])

  // Station local outbox
  const stationLocalOutbox = useMemo(
    () => localOutboxItems.filter((item) => item.sender_endpoint_id === stationId),
    [localOutboxItems, stationId]
  )

  // Aggregate Counters
  const outboxCount = outboxMessages.length
  const localCount = stationLocalOutbox.length
  const deliveredCount = outboxMessages.filter((m) => m.current_state === 'DELIVERED').length
  const inboxCount = inboxMessages.length

  // Combined and sorted chronological feed
  const feedEntries: FeedEntry[] = useMemo(() => {
    const entries: FeedEntry[] = []

    if (activeFilter === 'all' || activeFilter === 'outbox') {
      outboxMessages.forEach((m) => {
        entries.push({
          id: `outbox-${m.message_id}`,
          kind: 'outbox',
          timestamp: new Date(m.created_at).getTime(),
          outboxMsg: m,
        })
      })

      stationLocalOutbox.forEach((item) => {
        entries.push({
          id: `local-${item.client_idempotency_key}`,
          kind: 'local_outbox',
          timestamp: new Date(item.created_at).getTime(),
          localOutboxItem: item,
        })
      })
    }

    if (activeFilter === 'all' || activeFilter === 'inbox') {
      inboxMessages.forEach((im) => {
        entries.push({
          id: `inbox-${im.inbox_id || im.message_id}`,
          kind: 'inbox',
          timestamp: new Date(im.stored_at || im.created_at).getTime(),
          inboxMsg: im,
        })
      })
    }

    return entries.sort((a, b) => a.timestamp - b.timestamp)
  }, [outboxMessages, inboxMessages, stationLocalOutbox, activeFilter])

  // Auto-scroll when messages update
  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [feedEntries.length])

  // Presets
  const presets = [
    { type: 'STATUS_REPORT', text: 'SITREP: All telemetry nominal. Node online.', prio: 1 },
    { type: 'TACTICAL_ORDER', text: 'ORDER: Initiate store-and-forward sync across ISM link.', prio: 2 },
    { type: 'BEACON', text: 'BEACON: Link heartbeat probe.', prio: 1 },
    { type: 'ALERT', text: 'FLASH: Priority anomaly detected on link perimeter.', prio: 4 },
  ]

  const handleApplyPreset = (preset: (typeof presets)[0]) => {
    onMessageTypeChange(preset.type)
    onComposerTextChange(preset.text)
    onPriorityChange(preset.prio)
  }

  // Keydown shortcut (Cmd+Enter or Ctrl+Enter)
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      if (composerText.trim() && !isSubmitting) {
        onSubmit()
      }
    }
  }

  const handleForceRequeue = async (e: React.MouseEvent, messageId: string) => {
    e.stopPropagation()
    try {
      await api.retryMessage(messageId)
      syncService.broadcastMutation()
    } catch (err) {
      console.error('Failed to force re-queue:', err)
    }
  }

  return (
    <div
      className={`flex flex-col h-full bg-[#0B0F17] rounded-xl border ${stationBorderColor} ${stationGlow} overflow-hidden`}
    >
      {/* 1. Dedicated Station Identity Banner */}
      <div className="bg-[#131B2E] border-b border-zinc-800/80 px-4 py-3 shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
          {/* Station Pill Badge */}
          <div className="flex items-center space-x-2">
            <span
              className={`font-mono text-xs font-bold px-2.5 py-1 rounded-md border flex items-center space-x-1.5 ${stationBadgeBg}`}
            >
              <span
                className="w-2 h-2 rounded-full animate-pulse"
                style={{ backgroundColor: stationAccent }}
              />
              <span>{stationName}</span>
              <span className="text-zinc-500 font-normal">({stationId})</span>
            </span>
            <div className="flex items-center space-x-1 text-[11px] text-zinc-400 font-mono">
              <ArrowRight className="w-3 h-3 text-zinc-500" />
              <span>Target:</span>
              <span className="text-zinc-300 font-semibold">{targetStationName}</span>
              <span className="text-zinc-500 font-normal">({targetStationId})</span>
            </div>
          </div>

          {/* Storage & Connection HUD */}
          <div className="flex items-center space-x-1.5">
            {/* Physical Storage Badge */}
            <span
              className="bg-zinc-800 text-zinc-300 font-mono text-[9px] px-1.5 py-0.5 rounded border border-zinc-700"
              title={`SQLite Write-Ahead Logging: ${dbPath || (isStationAlpha ? 'alpha.db' : 'bravo.db')}`}
            >
              STORAGE: {dbPath || (isStationAlpha ? 'alpha.db' : 'bravo.db')} (WAL)
            </span>

            {/* Daemon Connection Pill */}
            <span
              className={`font-mono text-[9px] px-1.5 py-0.5 rounded border flex items-center space-x-1 ${
                isDaemonOnline
                  ? isStationAlpha
                    ? 'bg-cyan-950/70 border-cyan-700/60 text-cyan-300'
                    : 'bg-emerald-950/70 border-emerald-700/60 text-emerald-300'
                  : 'bg-rose-950/80 border-rose-600/80 text-rose-300 animate-pulse'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isDaemonOnline ? (isStationAlpha ? 'bg-cyan-400' : 'bg-emerald-400') : 'bg-rose-400 animate-ping'
                }`}
              />
              <span>
                {isDaemonOnline
                  ? `CONNECTED :${stationPort || (isStationAlpha ? 5051 : 5052)}`
                  : `DAEMON OFFLINE :${stationPort || (isStationAlpha ? 5051 : 5052)}`}
              </span>
            </span>
          </div>

          {/* Radio Link Telemetry HUD */}
          <div className="flex items-center space-x-2 text-[10px] font-mono text-zinc-400 bg-[#0B0F17]/80 px-2.5 py-1 rounded border border-zinc-800">
            <span className="flex items-center space-x-1">
              <Radio className="w-3 h-3 text-cyan-400" />
              <span className="text-zinc-300">2.484 GHz ISM Ch 14</span>
            </span>
            <span className="text-zinc-600">&bull;</span>
            <span className="text-zinc-300">245.76 kS/s</span>
            <span className="text-zinc-600">&bull;</span>
            {isLinkOnline ? (
              <span className="flex items-center space-x-1 text-emerald-400 font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                <span>Online</span>
              </span>
            ) : (
              <span className="flex items-center space-x-1 text-rose-400 font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-pulse" />
                <span>Air-Gap</span>
              </span>
            )}
          </div>
        </div>

        {/* Real-time counters & Filter Tabs */}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-zinc-800/60">
          {/* Real-time Queue Counters */}
          <div className="flex items-center space-x-3 text-[11px] font-mono">
            <div className="flex items-center space-x-1">
              <span className="text-zinc-500">Outbox:</span>
              <span className="text-zinc-200 font-semibold">{outboxCount}</span>
              {localCount > 0 && (
                <span className="text-amber-400 font-bold ml-0.5">
                  (+{localCount} local)
                </span>
              )}
            </div>
            <div className="flex items-center space-x-1">
              <span className="text-zinc-500">Delivered:</span>
              <span className="text-emerald-400 font-semibold">{deliveredCount}</span>
            </div>
            <div className="flex items-center space-x-1">
              <span className="text-zinc-500">Verified Inbox:</span>
              <span className="text-emerald-300 font-semibold">{inboxCount}</span>
            </div>
          </div>

          {/* Filter Tabs */}
          <div className="flex items-center bg-[#0B0F17] rounded-md p-0.5 border border-zinc-800 text-[10px] font-mono">
            <button
              onClick={() => setActiveFilter('all')}
              className={`px-2 py-0.5 rounded transition-all ${
                activeFilter === 'all'
                  ? 'bg-zinc-800 text-zinc-100 font-bold shadow'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              All Feeds ({outboxCount + localCount + inboxCount})
            </button>
            <button
              onClick={() => setActiveFilter('outbox')}
              className={`px-2 py-0.5 rounded transition-all ${
                activeFilter === 'outbox'
                  ? 'bg-zinc-800 text-zinc-100 font-bold shadow'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Outbox ({outboxCount + localCount})
            </button>
            <button
              onClick={() => setActiveFilter('inbox')}
              className={`px-2 py-0.5 rounded transition-all ${
                activeFilter === 'inbox'
                  ? 'bg-emerald-950/80 text-emerald-300 font-bold border border-emerald-500/40 shadow'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Inbox ({inboxCount})
            </button>
          </div>
        </div>
      </div>

      {/* 2. Scrollable Message Feed Container */}
      <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-2.5">
        {feedEntries.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-zinc-500">
            <div className="p-3 bg-zinc-900/60 rounded-full border border-zinc-800 mb-2">
              <Radio className="w-8 h-8 text-zinc-600 animate-pulse" />
            </div>
            <h4 className="font-semibold text-zinc-300 text-sm mb-1">No Messages in Feed</h4>
            <p className="text-xs text-zinc-500 max-w-xs">
              Submit a message to initiate store-and-forward transmission.
            </p>
          </div>
        ) : (
          feedEntries.map((entry) => {
            // Local outbox items (IndexedDB offline store)
            if (entry.kind === 'local_outbox' && entry.localOutboxItem) {
              const item = entry.localOutboxItem
              return (
                <div
                  key={entry.id}
                  className="bg-[#18181B] border border-amber-500/50 shadow-[0_4px_24px_rgba(245,158,11,0.2)] rounded-lg p-3 transition-all relative overflow-hidden"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="bg-amber-950/80 border border-amber-500/60 text-amber-300 font-mono text-[9px] font-bold px-2 py-0.5 rounded shadow-[0_0_8px_rgba(245,158,11,0.3)] flex items-center space-x-1">
                      <HardDrive className="w-3 h-3 text-amber-400" />
                      <span>LOCAL STORED (INDEXEDDB)</span>
                    </span>
                    <span className="bg-zinc-800 text-amber-300 font-mono text-[9px] font-bold px-2 py-0.5 rounded border border-zinc-700 animate-pulse">
                      PENDING SYNC
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[10px] font-mono text-zinc-400 mb-2">
                    <span>Composed: {formatMicroseconds(item.created_at)}</span>
                    <span className="text-amber-400/90 font-semibold">Server Queued: PENDING</span>
                  </div>
                  <div className="bg-[#0B0F17]/80 rounded p-2 border border-zinc-800/80 mb-2 font-mono text-xs text-zinc-200">
                    {item.payload}
                  </div>
                  <div className="flex items-center justify-between pt-1 border-t border-zinc-800/60 text-[10px] font-mono">
                    <span className="text-zinc-500 truncate select-all">
                      KEY: {item.client_idempotency_key}
                    </span>
                    <button
                      type="button"
                      onClick={() => (onFlushOutbox ? onFlushOutbox() : syncService.flushOutbox())}
                      className="px-2.5 py-1 rounded bg-amber-600 hover:bg-amber-500 text-white font-mono text-[10px] font-bold shadow transition-colors cursor-pointer flex items-center space-x-1"
                    >
                      <RefreshCw className="w-2.5 h-2.5" />
                      <span>Flush Now</span>
                    </button>
                  </div>
                </div>
              )
            }

            if (entry.kind === 'inbox' && entry.inboxMsg) {
              const im = entry.inboxMsg
              const isSelected = selectedMessage?.message_id === im.message_id
              return (
                <InboxReceiptCard
                  key={entry.id}
                  inboxItem={im}
                  isSelected={isSelected}
                  onClick={() => {
                    const fallbackMsg: Message = {
                      message_id: im.message_id,
                      client_idempotency_key: im.message_id,
                      sender_endpoint_id: im.sender_endpoint_id,
                      recipient_endpoint_id: im.recipient_endpoint_id,
                      payload: im.payload,
                      message_type: im.message_type,
                      incident_id: im.incident_id,
                      current_state: im.current_state || 'DELIVERED',
                      retry_count: 0,
                      max_retries: 5,
                      next_retry_at: null,
                      expires_at: null,
                      created_at: im.created_at,
                      updated_at: im.stored_at || im.created_at,
                      delivered_at: im.stored_at || im.created_at,
                      priority: im.priority,
                      signed_ack_receipt: im.signed_ack_receipt || null,
                    }
                    onSelectMessage(fallbackMsg)
                  }}
                />
              )
            }

            if (entry.kind === 'outbox' && entry.outboxMsg) {
              const m = entry.outboxMsg
              const isSelected = selectedMessage?.message_id === m.message_id
              const isDelivered = m.current_state === 'DELIVERED'
              const isSending = m.current_state === 'SENDING' || m.current_state === 'AWAITING_ACK'
              const isRetryable = m.current_state === 'FAILED_RETRYABLE'
              const isPermanentFail = m.current_state === 'FAILED_FINAL'
              const formattedTime = formatMicroseconds(m.created_at)
              const isHighlighted = duplicateHighlightId === m.message_id

              // Reconcile receipt with inbox item if available
              const inboxItem = allInboxMap.get(m.message_id)
              const receiptSig = m.signed_ack_receipt || inboxItem?.signed_ack_receipt

              // Permanent failure card style (D-16)
              if (isPermanentFail) {
                return (
                  <div
                    key={entry.id}
                    onClick={() => onSelectMessage(m)}
                    className={`rounded-lg p-3 transition-all cursor-pointer relative overflow-hidden bg-[#1C1917] border border-rose-500/60 shadow-[0_4px_24px_rgba(239,68,68,0.25)] ${
                      isHighlighted ? 'ring-2 ring-cyan-400 shadow-[0_0_25px_rgba(6,182,212,0.4)]' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <div className="flex items-center space-x-1.5 text-xs font-mono text-zinc-300 truncate">
                        <span className="text-rose-400 font-semibold">{m.sender_endpoint_id}</span>
                        <ArrowRight className="w-3 h-3 text-zinc-500 shrink-0" />
                        <span className="text-zinc-400 font-semibold">{m.recipient_endpoint_id}</span>
                        {(m.pqc_verified || m.envelope_version === 3) && (
                          <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-mono border border-cyan-500/40 bg-cyan-950/30 text-cyan-300">
                            <ShieldCheck className="w-3 h-3 text-cyan-400" />
                            <span>PQC SECURED</span>
                          </span>
                        )}
                        {(m.pqc_downgrade_warning || m.envelope_version === 2) && (
                          <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-mono border border-amber-500/40 bg-amber-950/30 text-amber-300">
                            <AlertTriangle className="w-3 h-3 text-amber-400" />
                            <span>CLASSICAL V2</span>
                          </span>
                        )}
                      </div>
                      <span className="bg-rose-950/90 border border-rose-500 text-rose-300 font-mono text-[9px] font-bold px-2 py-0.5 rounded shadow-[0_0_8px_rgba(239,68,68,0.4)]">
                        Retry Limit Exhausted [5/5]
                      </span>
                    </div>

                    <div className="bg-[#0B0F17]/80 rounded p-2 border border-rose-900/60 mb-2 font-mono text-xs text-rose-200">
                      {m.payload}
                    </div>

                    <div className="flex items-center justify-between pt-1 border-t border-rose-900/50 text-[10px] font-mono">
                      <span className="text-zinc-500 truncate">UUID: {m.message_id.substring(0, 16)}...</span>
                      <button
                        type="button"
                        onClick={(e) => handleForceRequeue(e, m.message_id)}
                        className="px-2.5 py-1 rounded bg-rose-700 hover:bg-rose-600 text-white font-mono text-[10px] font-bold shadow-[0_0_10px_rgba(239,68,68,0.3)] transition-all flex items-center space-x-1 cursor-pointer active:translate-y-0.5"
                      >
                        <RotateCcw className="w-2.5 h-2.5" />
                        <span>Force Re-Queue Transmission</span>
                      </button>
                    </div>
                  </div>
                )
              }

              return (
                <div
                  key={entry.id}
                  onClick={() => onSelectMessage(m)}
                  className={`rounded-lg p-3 transition-all cursor-pointer relative overflow-hidden group ${
                    isHighlighted
                      ? 'ring-2 ring-cyan-400 shadow-[0_0_25px_rgba(6,182,212,0.4)] bg-[#1E293B] border border-cyan-400'
                      : isSelected
                      ? 'bg-[#1E293B] border border-cyan-400 ring-1 ring-cyan-400/50 shadow-[0_4px_24px_rgba(6,182,212,0.2)]'
                      : 'bg-[#131B2E] hover:bg-[#1E293B] border border-zinc-800 shadow-[0_4px_16px_rgba(0,0,0,0.3)]'
                  }`}
                >
                  {/* Top Bar: Route & Status Pill */}
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <div className="flex items-center space-x-1.5 text-xs font-mono text-zinc-300 truncate">
                      <span className="text-cyan-300 font-semibold">{m.sender_endpoint_id}</span>
                      <ArrowRight className="w-3 h-3 text-zinc-500 shrink-0" />
                      <span className="text-zinc-400 font-semibold">{m.recipient_endpoint_id}</span>
                      {m.message_type && (
                        <span className="ml-1 text-[10px] bg-zinc-800 border border-zinc-700 text-zinc-400 px-1.5 py-0.2 rounded font-sans uppercase">
                          {m.message_type}
                        </span>
                      )}
                      {(m.pqc_verified || m.envelope_version === 3) && (
                        <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-mono border border-cyan-500/40 bg-cyan-950/30 text-cyan-300">
                          <ShieldCheck className="w-3 h-3 text-cyan-400" />
                          <span>PQC SECURED</span>
                        </span>
                      )}
                      {(m.pqc_downgrade_warning || m.envelope_version === 2) && (
                        <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-mono border border-amber-500/40 bg-amber-950/30 text-amber-300">
                          <AlertTriangle className="w-3 h-3 text-amber-400" />
                          <span>CLASSICAL V2</span>
                        </span>
                      )}
                    </div>

                    {/* Transmission State Pill */}
                    <div className="flex items-center space-x-1.5 shrink-0">
                      {isDelivered && (
                        <span className="bg-emerald-950/80 border border-emerald-500/60 text-emerald-300 font-mono text-[9px] font-bold px-2 py-0.5 rounded shadow-[0_0_8px_rgba(16,185,129,0.25)] flex items-center space-x-1">
                          <CheckCheck className="w-3 h-3 text-emerald-400 shrink-0" />
                          <span>ACK Verified</span>
                        </span>
                      )}
                      {isSending && (
                        <span className="bg-blue-950/80 border border-blue-500/50 text-blue-300 font-mono text-[9px] font-bold px-2 py-0.5 rounded flex items-center space-x-1 animate-pulse">
                          <Activity className="w-3 h-3 text-blue-400 shrink-0" />
                          <span>{m.current_state}</span>
                        </span>
                      )}
                      {isRetryable && (
                        <RetryCountdownBadge
                          nextRetryAt={m.next_retry_at}
                          retryCount={m.retry_count}
                          maxRetries={m.max_retries}
                        />
                      )}
                      {m.current_state === 'QUEUED' && (
                        <span className="bg-zinc-800 border border-zinc-700 text-zinc-300 font-mono text-[9px] font-bold px-2 py-0.5 rounded flex items-center space-x-1">
                          <Clock className="w-3 h-3 text-zinc-400 shrink-0" />
                          <span>QUEUED</span>
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Timestamp & Priority */}
                  <div className="flex items-center justify-between text-[10px] font-mono text-zinc-500 mb-2">
                    <span>Sent: {formattedTime}</span>
                    <span className="text-zinc-400">Prio: {m.priority}</span>
                  </div>

                  {/* Payload Preview */}
                  <div className="bg-[#0B0F17]/70 rounded p-2 border border-zinc-800/80 mb-2">
                    <p className="font-mono text-xs text-zinc-200 break-words whitespace-pre-wrap leading-relaxed line-clamp-3">
                      {m.payload}
                    </p>
                  </div>

                  {/* Footer: Receipt Signature & Delivery Info */}
                  {receiptSig && (
                    <div className="flex items-center justify-between pt-1 border-t border-zinc-800/60 text-[10px] font-mono text-emerald-400/90">
                      <span className="flex items-center space-x-1 truncate">
                        <Key className="w-2.5 h-2.5 shrink-0 text-emerald-400" />
                        <span className="truncate">
                          {receiptSig.length > 24 ? `${receiptSig.substring(0, 24)}...` : receiptSig}
                        </span>
                      </span>
                      {m.delivered_at && (
                        <span className="text-zinc-500 text-[9px] shrink-0">
                          ACK: {formatMicroseconds(m.delivered_at).split(' ')[1] || '—'}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )
            }

            return null
          })
        )}
        <div ref={feedEndRef} />
      </div>

      {/* 3. Dedicated Quick Composer Bar */}
      <div className="bg-[#131B2E] border-t border-zinc-800/90 p-3 shrink-0 space-y-2">
        {/* Presets Row */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] font-mono text-zinc-500 uppercase">Presets:</span>
          {presets.map((p) => (
            <button
              key={p.type}
              type="button"
              onClick={() => handleApplyPreset(p)}
              className={`text-[10px] font-mono px-2 py-0.5 rounded transition-all border ${
                messageType === p.type
                  ? 'bg-cyan-950/80 border-cyan-500/60 text-cyan-300 font-bold'
                  : 'bg-zinc-900 hover:bg-zinc-800 border-zinc-700/60 text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {p.type}
            </button>
          ))}
        </div>

        {/* Priority & Airtime HUD Row */}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-zinc-800/60 text-[10px] font-mono">
          {/* Priority selector */}
          <div className="flex items-center space-x-1">
            <span className="text-zinc-500">Prio:</span>
            {[
              { val: 1, label: 'NORM' },
              { val: 2, label: 'HIGH' },
              { val: 3, label: 'URG' },
              { val: 4, label: 'FLASH' },
            ].map((p) => (
              <button
                key={p.val}
                type="button"
                onClick={() => onPriorityChange(p.val)}
                className={`px-1.5 py-0.5 rounded font-bold border transition-all ${
                  priority === p.val
                    ? p.val === 4
                      ? 'bg-red-950 border-red-500 text-red-300'
                      : p.val === 3
                      ? 'bg-amber-950 border-amber-500 text-amber-300'
                      : p.val === 2
                      ? 'bg-blue-950 border-blue-500 text-blue-300'
                      : 'bg-zinc-700 border-zinc-500 text-zinc-100'
                    : 'bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-zinc-300'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Real-Time Tactical RF & DMR Burst Budget HUD */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center space-x-2 text-zinc-400 bg-[#0B0F17]/90 px-2 py-0.5 rounded border border-zinc-800/80">
              <span>
                Raw: <strong className="text-zinc-200">{rfMetrics.rawBytes}B</strong>
              </span>
              <span>
                PQC Env: <strong className="text-cyan-300">+{rfMetrics.rawBytes > 0 ? 1150 : 0}B</strong>
              </span>
              <span>
                RS: <strong className="text-zinc-200">{rfMetrics.rsChunks} blk</strong>
              </span>
              <span className="text-cyan-400">
                Burst: <strong>{rfMetrics.burstAirtimeMs} ms</strong>
              </span>
            </div>

            <div className="flex items-center space-x-1.5 text-[11px] font-mono text-cyan-400 bg-cyan-950/20 px-2 py-0.5 rounded border border-cyan-500/30 shadow-[0_0_10px_rgba(6,182,212,0.15)]">
              <Radio className="w-3 h-3 text-cyan-400 animate-pulse" />
              <span>
                DMR: <strong className="text-zinc-100">{rfMetrics.dmrChunks} {rfMetrics.dmrChunks === 1 ? 'Burst' : 'Bursts'}</strong> ({rfMetrics.dmrWireBudget} B Wire Budget • PQC Hybrid Encapsulation)
              </span>
            </div>
          </div>
        </div>

        {/* Offline Daemon Notice */}
        {!isDaemonOnline && (
          <div className="bg-amber-950/60 border border-amber-600/60 text-amber-300 font-mono text-[10px] px-2 py-1 rounded flex items-center space-x-1.5 mb-1.5">
            <HardDrive className="w-3 h-3 text-amber-400 shrink-0" />
            <span>
              Station daemon unreachable on port :{stationPort || (isStationAlpha ? 5051 : 5052)}. Messages will be stored in browser IndexedDB outbox.
            </span>
          </div>
        )}

        {/* Text Input & Submit CTA */}
        <div className="flex items-end gap-2 pt-1">
          <textarea
            value={composerText}
            onChange={(e) => onComposerTextChange(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={isSplitMode ? 2 : 3}
            placeholder={`Transmit tactical packet from ${stationName} to ${targetStationName}...`}
            className="flex-1 bg-[#0B0F17] border border-zinc-700/80 focus:border-cyan-500 rounded-lg p-2 text-xs font-mono text-zinc-100 placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-cyan-500/50 resize-none transition-all"
          />

          <button
            type="button"
            onClick={() => onSubmit()}
            disabled={!composerText.trim() || isSubmitting}
            className={`px-3 py-2 rounded-lg font-mono text-xs font-bold flex items-center space-x-1.5 transition-all shadow-md shrink-0 ${
              !composerText.trim() || isSubmitting
                ? 'bg-zinc-800 text-zinc-500 border border-zinc-700/40 cursor-not-allowed opacity-60'
                : !isLinkOnline
                ? 'bg-amber-600 hover:bg-amber-500 text-white shadow-[0_0_15px_rgba(245,158,11,0.3)] active:translate-y-0.5'
                : isStationAlpha
                ? 'bg-cyan-600 hover:bg-cyan-500 text-white shadow-[0_0_15px_rgba(6,182,212,0.3)] active:translate-y-0.5'
                : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-[0_0_15px_rgba(16,185,129,0.3)] active:translate-y-0.5'
            }`}
          >
            {isSubmitting ? (
              <>
                <RotateCcw className="w-3.5 h-3.5 animate-spin" />
                <span>Transmitting...</span>
              </>
            ) : !isLinkOnline ? (
              <>
                <HardDrive className="w-3.5 h-3.5" />
                <span>Store Locally (Offline Outbox)</span>
              </>
            ) : (
              <>
                <Send className="w-3.5 h-3.5" />
                <span>Transmit Packet</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
