import { Message, MessageEvent, QueueStats, AdapterStatus, AuditLogEntry } from '../types'

const BASE_URL = '/api/v1'

class ApiClient {
  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    })

    if (!res.ok) {
      let errorMsg = `HTTP Error ${res.status}`
      try {
        const errJson = await res.json()
        if (errJson.detail) errorMsg = errJson.detail
      } catch {
        // fallback
      }
      throw new Error(errorMsg)
    }

    return res.json() as Promise<T>
  }

  async getHealth(): Promise<{ status: string; service: string; version: string; mode: string }> {
    return this.request('/health')
  }

  async getQueueStats(): Promise<QueueStats> {
    return this.request('/queue/stats')
  }

  async getMessages(params?: { sender?: string; recipient?: string; state?: string }): Promise<Message[]> {
    const query = new URLSearchParams()
    if (params?.sender) query.append('sender', params.sender)
    if (params?.recipient) query.append('recipient', params.recipient)
    if (params?.state) query.append('state', params.state)
    const qs = query.toString() ? `?${query.toString()}` : ''
    return this.request(`/messages${qs}`)
  }

  async getMessage(messageId: string): Promise<Message> {
    return this.request(`/messages/${messageId}`)
  }

  async getMessageEvents(messageId: string): Promise<MessageEvent[]> {
    return this.request(`/messages/${messageId}/events`)
  }

  async submitMessage(data: {
    client_idempotency_key: string
    sender_endpoint_id: string
    recipient_endpoint_id: string
    payload: string
    priority?: number
    expires_in_seconds?: number
  }): Promise<Message> {
    return this.request('/messages', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async retryMessage(messageId: string): Promise<Message> {
    return this.request(`/messages/${messageId}/retry`, {
      method: 'POST',
    })
  }

  async cancelMessage(messageId: string): Promise<Message> {
    return this.request(`/messages/${messageId}/cancel`, {
      method: 'POST',
    })
  }

  async getAdapters(): Promise<AdapterStatus[]> {
    return this.request('/adapters')
  }

  async getEndpoints(): Promise<any[]> {
    return this.request('/endpoints')
  }

  async configureSimulation(config: {
    is_online?: boolean
    latency_ms?: number
    packet_drop_rate?: number
    ack_drop_rate?: number
  }): Promise<any> {
    return this.request('/adapters/simulation/status', {
      method: 'POST',
      body: JSON.stringify(config),
    })
  }

  async injectFault(faultType: string): Promise<any> {
    return this.request(`/adapters/simulation/faults/${faultType}`, {
      method: 'POST',
    })
  }

  async getAuditLogs(): Promise<AuditLogEntry[]> {
    return this.request('/audit/logs')
  }
}

export const api = new ApiClient()
