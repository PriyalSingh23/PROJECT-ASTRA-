import {
  Message,
  InboxMessage,
  MessageEvent,
  QueueStats,
  Endpoint,
  TransportAdapter,
  RelayNode,
  AuthSession,
  AuditLogEntry,
  CheckpointsAudit,
  CheckpointVerifyResponse,
  TamperSimResponse,
  ComparativeBenchmarkResult,
  TrainingEpoch,
  EvaluationReport,
  AnomalyReport,
  WaveformComparison,
  SignalSample,
  EnvironmentMetadata,
  WorkstationOverview,
  SDRHardwareStatus,
  TransmitterPreparation,
  ReceiverDSPPipelineResult,
  ChannelSimulationResult,
  SignalIntelligenceData,
  SystemDiagnosticsData,
  StarVTestResult,
  StationHealthMetadata,
  KeyringInfo,
  RotateKeysResponse,
  TamperTestResponse,
  MeshNode,
  MeshLink,
  MeshActiveRoute,
  MeshTopologyData,
  MeshScenarioResponse,
} from '../types'

const BASE_URL = '/api/v1'

export class ApiClient {
  private token: string | null = null
  private baseUrl: string

  constructor(baseUrl: string = BASE_URL) {
    this.baseUrl = baseUrl.replace(/\/$/, '')
    this.token = typeof localStorage !== 'undefined' ? localStorage.getItem('shadowcomm_auth_token') : null
  }

  setToken(token: string | null) {
    this.token = token
    if (typeof localStorage !== 'undefined') {
      if (token) {
        localStorage.setItem('shadowcomm_auth_token', token)
      } else {
        localStorage.removeItem('shadowcomm_auth_token')
      }
    }
  }

  getToken(): string | null {
    if (this.token) return this.token
    if (typeof localStorage !== 'undefined') {
      return localStorage.getItem('shadowcomm_auth_token')
    }
    return null
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...((options?.headers as Record<string, string>) || {}),
    }

    const currentToken = this.getToken()
    if (currentToken && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${currentToken}`
    }

    const res = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers,
    })

    if (!res.ok) {
      let errorMsg = `HTTP Error ${res.status}`
      try {
        const errJson = await res.json()
        if (errJson.error) errorMsg = errJson.error
        else if (errJson.detail) errorMsg = errJson.detail
      } catch {
        // Fallback to HTTP text
      }
      throw new Error(errorMsg)
    }

    return res.json() as Promise<T>
  }

  // ==================== AUTHENTICATION ====================
  async login(username: string, password: string): Promise<AuthSession> {
    const res = await this.request<AuthSession>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    if (res.token) {
      this.setToken(res.token)
    }
    return res
  }

  async logout(): Promise<void> {
    try {
      await this.request('/auth/logout', { method: 'POST' })
    } catch {
      // Ignore network errors on logout
    } finally {
      this.setToken(null)
    }
  }

  async getMe(): Promise<any> {
    return this.request('/auth/me')
  }

  async getSecurityLogs(limit: number = 50): Promise<AuditLogEntry[]> {
    return this.request(`/security/audit-logs?limit=${limit}`)
  }

  // ==================== HEALTH & STATS ====================
  async getHealth(): Promise<StationHealthMetadata> {
    return this.request<StationHealthMetadata>('/health')
  }

  async getQueueStats(): Promise<QueueStats> {
    return this.request('/queue/stats')
  }

  // ==================== MESSAGING ====================
  async getEndpoints(): Promise<Endpoint[]> {
    return this.request('/endpoints')
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
    message_type?: string
    incident_id?: string
    priority?: number
    expires_in_seconds?: number
  }): Promise<Message> {
    return this.request('/messages', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async retryMessage(messageId: string): Promise<Message> {
    return this.request(`/messages/${messageId}/retry`, { method: 'POST' })
  }

  async cancelMessage(messageId: string): Promise<Message> {
    return this.request(`/messages/${messageId}/cancel`, { method: 'POST' })
  }

  async getInbox(endpointId: string): Promise<InboxMessage[]> {
    return this.request(`/endpoints/${endpointId}/inbox`)
  }

  async getOutbox(endpointId: string): Promise<Message[]> {
    return this.request(`/endpoints/${endpointId}/outbox`)
  }

  // ==================== HARDWARE & TRANSPORTS ====================
  async getTransports(): Promise<TransportAdapter[]> {
    return this.request('/transports')
  }

  async getActiveTransport(): Promise<{
    active_transport: string | null
    mode: string
    is_live: boolean
    auto_failover: boolean
    bridge?: any
  }> {
    return this.request('/transports/active')
  }

  async setActiveTransport(transportId: string | null, autoFailover?: boolean): Promise<any> {
    return this.request('/transports/active', {
      method: 'POST',
      body: JSON.stringify({ transport_id: transportId, auto_failover: autoFailover }),
    })
  }

  async setAutoFailover(autoFailover: boolean): Promise<{ auto_failover: boolean; active_transport: string | null }> {
    return this.request('/transports/failover', {
      method: 'POST',
      body: JSON.stringify({ auto_failover: autoFailover }),
    })
  }

  async testStarVLockout(testType: 'soft_refusal' | 'hard_command'): Promise<StarVTestResult> {
    return this.request('/transports/starv/test-lockout', {
      method: 'POST',
      body: JSON.stringify({ test_type: testType }),
    })
  }

  async getTransportDetail(transportId: string): Promise<any> {
    return this.request(`/transports/${transportId}`)
  }

  async getRelays(): Promise<RelayNode[]> {
    return this.request('/relays')
  }

  async getRelay(relayId: string): Promise<RelayNode> {
    return this.request(`/relays/${relayId}`)
  }

  async updateRelayTelemetry(
    relayId: string,
    data: { battery?: number; temperature?: number; storage_pct?: number; status?: string; queue_depth?: number }
  ): Promise<RelayNode> {
    return this.request(`/relays/${relayId}/telemetry`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async resetRelayTelemetry(relayId: string): Promise<RelayNode> {
    return this.request(`/relays/${relayId}/reset`, {
      method: 'POST',
    })
  }

  // ==================== SIMULATION CONTROL ====================
  async getSimTransport(): Promise<any> {
    return this.request('/sim/transport')
  }

  async updateSimTransport(config: {
    is_online?: boolean
    latency_ms?: number
    drop_message_prob?: number
    drop_ack_prob?: number
    preset?: string
    reset?: boolean
  }): Promise<any> {
    return this.request('/sim/transport', {
      method: 'POST',
      body: JSON.stringify(config),
    })
  }

  async injectFault(data: { message_id: string; action: string; error_code?: string }): Promise<any> {
    return this.request('/sim/faults', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async armFault(action: string): Promise<any> {
    return this.request('/sim/faults', {
      method: 'POST',
      body: JSON.stringify({ message_id: '*', action }),
    })
  }

  async disarmAllFaults(): Promise<any> {
    return this.request('/sim/faults', {
      method: 'POST',
      body: JSON.stringify({ message_id: '*', action: 'disarm_all' }),
    })
  }

  async triggerLeaseReclaim(): Promise<{ reclaimed_count: number; timestamp: string }> {
    return this.request('/worker/reclaim', { method: 'POST' })
  }

  async simulateWorkerCrash(messageId?: string): Promise<{ status: string; message_id: string; worker_lease_id: string; lease_expires_at: string }> {
    return this.request('/worker/crash-simulation', {
      method: 'POST',
      body: JSON.stringify(messageId ? { message_id: messageId } : {}),
    })
  }

  async getRetryProfile(): Promise<{ active_profile: 'FAST' | 'TACTICAL'; base_delay: number; max_delay: number; jitter: number }> {
    return this.request('/worker/retry-profile')
  }

  async setRetryProfile(profile: 'FAST' | 'TACTICAL'): Promise<{ active_profile: 'FAST' | 'TACTICAL'; base_delay: number; max_delay: number; jitter: number }> {
    return this.request('/worker/retry-profile', {
      method: 'POST',
      body: JSON.stringify({ profile }),
    })
  }

  // ==================== SCIENTIFIC RESEARCH LAB ====================
  async getResearchStatus(): Promise<any> {
    return this.request('/research/status')
  }

  async getResearchCheckpoints(): Promise<CheckpointsAudit> {
    return this.request('/research/checkpoints')
  }

  async verifyCheckpoint(): Promise<CheckpointVerifyResponse> {
    return this.request('/research/checkpoints/verify', { method: 'POST' })
  }

  async testTamper(tamper: boolean): Promise<TamperSimResponse> {
    return this.request('/research/checkpoints/test-tamper', {
      method: 'POST',
      body: JSON.stringify({ tamper }),
    })
  }

  async runComparativeBenchmark(frames: number = 64): Promise<ComparativeBenchmarkResult> {
    return this.request('/research/benchmark/compare', {
      method: 'POST',
      body: JSON.stringify({ frames }),
    })
  }

  async getTrainingHistory(limit: number = 75): Promise<TrainingEpoch[]> {
    return this.request(`/research/training-history?limit=${limit}`)
  }

  async getEvaluationReport(): Promise<EvaluationReport> {
    return this.request('/research/evaluation')
  }

  async getSignalSample(n: number = 256): Promise<SignalSample> {
    return this.request(`/research/signal-sample?n=${n}`)
  }

  async getEnvironmentMetadata(): Promise<EnvironmentMetadata> {
    return this.request('/research/environment')
  }

  async runControlledEval(frames: number = 128, snrs: string = '2,6,10', device: string = 'cpu'): Promise<any> {
    return this.request('/research/eval/run', {
      method: 'POST',
      body: JSON.stringify({ frames, snrs, device }),
    })
  }

  async getAnomalies(frames: number = 32): Promise<AnomalyReport> {
    return this.request(`/research/anomalies?frames=${frames}`)
  }

  async getWaveformComparison(frames: number = 4): Promise<WaveformComparison> {
    return this.request(`/research/waveform-comparison?frames=${frames}`)
  }

  // ==================== ASTRA WORKSTATION ====================
  async getWorkstationOverview(): Promise<WorkstationOverview> {
    return this.request('/workstation/overview')
  }

  async getSDRHardwareStatus(): Promise<SDRHardwareStatus> {
    return this.request('/workstation/sdr-status')
  }

  async prepareTransmitterPayload(text: string, message_type: string = 'TEXT'): Promise<TransmitterPreparation> {
    return this.request('/workstation/transmitter/prepare', {
      method: 'POST',
      body: JSON.stringify({ text, message_type }),
    })
  }

  async generateWaveformBurst(text: string): Promise<any> {
    return this.request('/workstation/transmitter/generate', {
      method: 'POST',
      body: JSON.stringify({ text }),
    })
  }

  async transmitBurst(text: string, mode: string = 'SIMULATION', confirm: boolean = true): Promise<any> {
    return this.request('/workstation/transmitter/transmit', {
      method: 'POST',
      body: JSON.stringify({ text, mode, confirm }),
    })
  }

  async captureAndProcessReceiver(
    mode: string = 'SIMULATION',
    target_snr_db: number = 6.0,
    payload_text?: string
  ): Promise<ReceiverDSPPipelineResult> {
    return this.request('/workstation/receiver/capture', {
      method: 'POST',
      body: JSON.stringify({ mode, target_snr_db, payload_text }),
    })
  }

  async simulateChannel(
    target_snr_db: number = 6.0,
    cfo_hz: number = 50.0,
    phase_offset_deg: number = 15.0,
    multipath: boolean = false
  ): Promise<ChannelSimulationResult> {
    return this.request('/workstation/channel/simulate', {
      method: 'POST',
      body: JSON.stringify({ target_snr_db, cfo_hz, phase_offset_deg, multipath }),
    })
  }

  async getSignalIntelligenceData(options?: {
    source?: 'SYNTHESIS' | 'RECORDED_IQ' | 'LIVE_SDR'
    fft_size?: number
    window?: string
    file?: string
  }): Promise<SignalIntelligenceData> {
    const params = new URLSearchParams()
    if (options?.source) params.append('source', options.source)
    if (options?.fft_size) params.append('fft_size', options.fft_size.toString())
    if (options?.window) params.append('window', options.window)
    if (options?.file) params.append('file', options.file)
    const qs = params.toString() ? `?${params.toString()}` : ''
    return this.request(`/workstation/signal/analysis${qs}`)
  }

  async getSystemDiagnostics(): Promise<SystemDiagnosticsData> {
    return this.request('/workstation/diagnostics')
  }

  async getWorkstationExperiments(): Promise<any> {
    return this.request('/workstation/experiments')
  }

  async getGlossary(): Promise<Record<string, import('../types').GlossaryItem>> {
    return this.request('/workstation/glossary')
  }

  async getHelpDocumentation(): Promise<import('../types').HelpDocumentation> {
    return this.request('/workstation/help')
  }

  // ==================== POST-QUANTUM CRYPTOGRAPHY ====================
  async getPublicKeys(): Promise<KeyringInfo> {
    return this.request<KeyringInfo>('/endpoints/public-keys')
  }

  async rotateKeys(): Promise<RotateKeysResponse> {
    return this.request<RotateKeysResponse>('/crypto/rotate-keys', { method: 'POST' })
  }

  async zeroizeKeyring(): Promise<{ status: string; detail: string; endpoint_id?: string; zeroized_at?: string }> {
    return this.request<{ status: string; detail: string; endpoint_id?: string; zeroized_at?: string }>('/crypto/zeroize', { method: 'POST' })
  }

  async simulateTamperTest(targetStationUrl?: string): Promise<TamperTestResponse> {
    return this.request<TamperTestResponse>('/crypto/test-tamper', {
      method: 'POST',
      body: JSON.stringify(targetStationUrl ? { target_station_url: targetStationUrl } : {}),
    })
  }

  // ==================== MULTI-HOP MESH ROUTING (PHASE 08) ====================
  async getMeshTopology(): Promise<MeshTopologyData> {
    return this.request<MeshTopologyData>('/topology/mesh')
  }

  async setRelayTelemetry(
    relayId: string,
    telemetry: { battery?: number; status?: string; queue_depth?: number; storage_pct?: number }
  ): Promise<any> {
    return this.request<any>(`/relays/${relayId}/telemetry`, {
      method: 'POST',
      body: JSON.stringify(telemetry),
    })
  }

  async triggerMeshScenario(scenario: string): Promise<MeshScenarioResponse> {
    return this.request<MeshScenarioResponse>('/relays/scenario', {
      method: 'POST',
      body: JSON.stringify({ scenario }),
    })
  }

  async simulateRoute(): Promise<any> {
    return this.request<any>('/mesh/route/simulate', {
      method: 'POST',
    })
  }
}

export const api = new ApiClient('/api/v1')

export const alphaApi = new ApiClient(
  typeof window !== 'undefined' && window.location.port === '5051'
    ? '/api/v1'
    : 'http://127.0.0.1:5051/api/v1'
)

export const bravoApi = new ApiClient(
  typeof window !== 'undefined' && window.location.port === '5052'
    ? '/api/v1'
    : 'http://127.0.0.1:5052/api/v1'
)

export function getStationApiClient(stationId: string): ApiClient {
  const normalized = stationId.toLowerCase()
  if (normalized === 'endpoint-a' || normalized.includes('alpha')) {
    return alphaApi
  }
  if (normalized === 'endpoint-b' || normalized.includes('bravo')) {
    return bravoApi
  }
  return api
}

// Exported convenience functions bound to default api
export const getPublicKeys = (client: ApiClient = api) => client.getPublicKeys()
export const rotateKeys = (client: ApiClient = api) => client.rotateKeys()
export const zeroizeKeyring = (client: ApiClient = api) => client.zeroizeKeyring()
export const simulateTamperTest = (targetStationUrl?: string, client: ApiClient = api) =>
  client.simulateTamperTest(targetStationUrl)
export const getMeshTopology = (client: ApiClient = api) => client.getMeshTopology()
export const setRelayTelemetry = (
  relayId: string,
  telemetry: { battery?: number; status?: string; queue_depth?: number; storage_pct?: number },
  client: ApiClient = api
) => client.setRelayTelemetry(relayId, telemetry)
export const triggerMeshScenario = (scenario: string, client: ApiClient = api) =>
  client.triggerMeshScenario(scenario)
export const simulateRoute = (client: ApiClient = api) => client.simulateRoute()




