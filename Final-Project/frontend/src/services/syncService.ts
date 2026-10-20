import { outboxDb } from './outboxDb'
import { api } from './api'

type SyncCallback = () => void

export interface FlushResult {
  flushed: number
  duplicates: number
  failed: number
}

class SyncService {
  private channel: BroadcastChannel | null = null
  private listeners: Set<SyncCallback> = new Set()
  private isFlushing: boolean = false

  constructor() {
    if (typeof window !== 'undefined' && 'BroadcastChannel' in window) {
      try {
        this.channel = new BroadcastChannel('shadowcomm_outbox_channel')
        this.channel.onmessage = (event) => {
          if (event.data?.type === 'OUTBOX_MUTATED') {
            this.notifyListeners()
          }
        }
      } catch {
        this.channel = null
      }
    }
    outboxDb.initPersistence().catch(() => {})
  }

  subscribe(cb: SyncCallback): () => void {
    this.listeners.add(cb)
    return () => this.listeners.delete(cb)
  }

  private notifyListeners() {
    this.listeners.forEach((cb) => {
      try {
        cb()
      } catch {
        // Suppress listener error
      }
    })
  }

  broadcastMutation() {
    this.notifyListeners()
    if (this.channel) {
      try {
        this.channel.postMessage({ type: 'OUTBOX_MUTATED', timestamp: Date.now() })
      } catch {
        // Fallback for channel errors
      }
    }
  }

  async flushOutbox(): Promise<FlushResult> {
    if (this.isFlushing) return { flushed: 0, duplicates: 0, failed: 0 }

    const executeFlush = async (): Promise<FlushResult> => {
      this.isFlushing = true
      let flushed = 0
      let duplicates = 0
      let failed = 0
      try {
        const items = await outboxDb.getAllMessages()
        const pending = items.filter((i) => i.sync_status === 'PENDING_LOCAL')

        for (const item of pending) {
          try {
            const res = await api.submitMessage({
              client_idempotency_key: item.client_idempotency_key,
              sender_endpoint_id: item.sender_endpoint_id,
              recipient_endpoint_id: item.recipient_endpoint_id,
              payload: item.payload,
              message_type: item.message_type || 'TEXT',
              priority: item.priority || 1,
              expires_in_seconds: item.expires_in_seconds || 86400,
            })
            // Seamless reconciliation: delete local item on both 201 (new) and 200 (duplicate)
            await outboxDb.deleteMessage(item.client_idempotency_key)
            if (res && res.is_new === false) {
              duplicates++
            } else {
              flushed++
            }
          } catch (err: any) {
            failed++
            await outboxDb.updateSyncStatus(
              item.client_idempotency_key,
              'FAILED_SYNC',
              err.message || 'Transmission failed'
            )
          }
        }
      } finally {
        this.isFlushing = false
        this.broadcastMutation()
      }
      return { flushed, duplicates, failed }
    }

    // Elect flush leader via Web Locks API if supported
    if (typeof navigator !== 'undefined' && 'locks' in navigator && navigator.locks.request) {
      try {
        return await navigator.locks.request(
          'shadowcomm_outbox_sync',
          { ifAvailable: true },
          async (lock) => {
            if (!lock) {
              // Another tab is currently flushing the outbox
              return { flushed: 0, duplicates: 0, failed: 0 }
            }
            return await executeFlush()
          }
        )
      } catch {
        return await executeFlush()
      }
    } else {
      // Fallback to in-process execution
      return await executeFlush()
    }
  }
}

export const syncService = new SyncService()
