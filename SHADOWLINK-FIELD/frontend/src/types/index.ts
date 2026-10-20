export type MessageState =
  | 'DRAFT'
  | 'QUEUED'
  | 'LEASED'
  | 'SENDING'
  | 'SENT_AWAITING_ACK'
  | 'ACK_RECEIVED'
  | 'DELIVERED'
  | 'FAILED_RETRYABLE'
  | 'FAILED_FINAL'
  | 'EXPIRED'
  | 'DUPLICATE_IGNORED'
  | 'CANCELLED'

export interface Message {
  message_id: string
  client_idempotency_key: string
  sender_endpoint_id: string
  recipient_endpoint_id: string
  payload: string
  message_type: string
  current_state: MessageState
  retry_count: number
  max_retries: number
  next_retry_at: string | null
  expires_at: string | null
  created_at: string
  updated_at: string
  delivered_at: string | null
  priority: number
  worker_lease_id?: string | null
  lease_expires_at?: string | null
}

export interface MessageEvent {
  event_id: string
  message_id: string
  event_type: string
  from_state?: string | null
  to_state?: string | null
  details?: Record<string, any>
  timestamp: string
}

export interface QueueStats {
  queued: number
  sending: number
  retry_waiting: number
  delivered: number
  failed_final: number
  expired: number
  cancelled: number
  total_messages: number
  active_leases: number
  transport?: {
    is_online: boolean
    latency_ms: number
    packet_drop_rate: number
    ack_drop_rate: number
    metrics: {
      packets_sent: number
      packets_delivered: number
      acks_sent: number
      acks_delivered: number
      packets_dropped: number
      acks_dropped: number
    }
  }
}

export interface AdapterStatus {
  adapter_id: string
  adapter_name: string
  version: string
  state: 'INITIALIZING' | 'READY' | 'BUSY' | 'DEGRADED' | 'LOCKED_OUT' | 'ERROR' | 'OFFLINE'
  mode: string
  is_hardware_connected: boolean
  is_transmitting_rf: boolean
  safety_lockout_active: boolean
  supported_features: string[]
  metrics: Record<string, any>
  description: string
}

export interface LocalOutboxItem {
  client_idempotency_key: string
  sender_endpoint_id: string
  recipient_endpoint_id: string
  payload: string
  priority: number
  expires_in_seconds: number
  created_at: string
  sync_status: 'PENDING_LOCAL' | 'SYNCED' | 'FAILED_SYNC'
  error_message?: string
}

export interface AuditLogEntry {
  audit_id: string
  action: string
  actor_user: string
  resource_type: string
  resource_id?: string | null
  details?: Record<string, any>
  timestamp: string
  outcome: string
}
