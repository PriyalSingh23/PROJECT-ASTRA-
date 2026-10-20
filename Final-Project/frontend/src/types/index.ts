export type MessageState =
  | 'DRAFT'
  | 'LOCAL_QUEUED'
  | 'LOCAL_PENDING'
  | 'QUEUED'
  | 'SENDING'
  | 'ACCEPTED'
  | 'AWAITING_ACK'
  | 'RECEIVED'
  | 'DELIVERED'
  | 'FAILED_RETRYABLE'
  | 'FAILED_FINAL'
  | 'EXPIRED'
  | 'CANCELLED'

export interface Message {
  message_id: string
  client_idempotency_key: string
  sender_endpoint_id: string
  recipient_endpoint_id: string
  payload: string
  message_type: string
  incident_id?: string | null
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
  signed_ack_receipt?: string | null
  last_error_code?: string | null
  is_new?: boolean
  envelope_version?: number
  pqc_scheme?: string | null
  pqc_verified?: boolean
  pqc_downgrade_warning?: boolean
}

export interface InboxMessage {
  inbox_id: string
  message_id: string
  sender_endpoint_id: string
  recipient_endpoint_id: string
  message_type: string
  incident_id?: string | null
  priority: number
  payload: string
  created_at: string
  stored_at: string
  integrity_status: string
  processing_status: string
  current_state: MessageState
  signed_ack_receipt?: string | null
  envelope_version?: number
  pqc_scheme?: string | null
  pqc_verified?: boolean
  pqc_downgrade_warning?: boolean
}

export interface MessageEvent {
  event_id: string
  message_id: string
  event_type: string
  from_state?: string | null
  to_state?: string | null
  error_code?: string | null
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
    drop_rate: number
    ack_drop_rate: number
    packets_sent: number
    packets_delivered: number
    acks_sent: number
    acks_delivered: number
    packets_dropped: number
    acks_dropped: number
  }
}

export interface Endpoint {
  endpoint_id: string
  display_name: string
  endpoint_type: string
  enabled: boolean
  last_seen_at?: string | null
  auth_token?: string | null
  created_at: string
  public_key_pqc?: string | null
  public_key_x25519?: string | null
  pqc_fingerprint?: string | null
  pqc_algorithm?: string | null
}

export interface TransportAdapter {
  transport_id: string
  display_name?: string
  transport_type: string
  readiness: 'READY' | 'SIMULATION_ONLY' | 'LOCKED_OUT' | 'OFFLINE' | 'UNAVAILABLE'
  connection_state: 'ONLINE' | 'OFFLINE' | 'STANDBY' | 'DEGRADED' | 'DISCONNECTED'
  supported_operations: string[]
  description?: string
  priority?: number
  metrics?: Record<string, any>
  last_operation_at?: string | null
  error_history?: any[]
  is_hardware_authorized?: boolean
}

export interface RelayNode {
  node_id: string
  display_name: string
  node_type: 'FIXED_GATEWAY' | 'PORTABLE_GROUND' | 'VEHICLE_GATEWAY' | 'AERIAL_PAYLOAD_SIMULATED' | string
  owner?: string
  status: 'ONLINE' | 'OFFLINE' | 'STANDBY' | 'MAINTENANCE' | 'STORAGE_FULL' | 'LOW_BATTERY' | string
  battery_percentage?: number
  battery_level_pct: number
  temperature_celsius: number
  storage_used_pct?: number
  storage_usage_pct: number
  connected_endpoints?: string[]
  queue_depth?: number
  queued_bundles_count?: number
  last_health_check_at?: string
  last_telemetry_at?: string
  last_forwarding_at?: string | null
  forwarded_message_count?: number
  flight_failsafe_independent?: boolean
  is_independent_payload?: boolean
  is_approved?: boolean
  failsafe_cutoff_active?: boolean
}

export interface StarVTestResult {
  status: 'BLOCKED'
  test_type: 'soft_refusal' | 'hard_command'
  mechanism: string
  details: string
  audit_logged: boolean
  timestamp?: string
}

export interface User {
  user_id: string
  username: string
  role: 'ADMINISTRATOR' | 'OPERATOR' | 'VIEWER'
  is_active: boolean
  failed_attempts: number
  created_at: string
}

export interface AuthSession {
  authenticated: boolean
  token: string
  user: User
  expires_at: string
}

export interface AuditLogEntry {
  log_id: string
  user_id?: string | null
  username?: string | null
  action: string
  ip_address?: string | null
  user_agent?: string | null
  details?: Record<string, any>
  timestamp: string
}

export interface CheckpointItem {
  path: string
  size_bytes: number
  sha256?: string | null
  generation: string
}

export interface CheckpointVerifyResponse {
  success: boolean
  verified: boolean
  sha256: string
  bundle_files: Record<string, { exists: boolean; size_bytes: number; path: string }>
  bundle_intact?: boolean
  audit_log_id: string
  fallback_active?: boolean
}

export interface TamperSimResponse {
  tamper_simulated: boolean
  fallback_active: boolean
  status: string
  audit_log_id: string
  details?: any
}

export interface ComparativeBenchmarkResult {
  frames: number
  cpu: { time_ms: number; ms_per_frame: number; throughput_fps: number }
  mps: { time_ms: number; ms_per_frame: number; throughput_fps: number; available: boolean; reason?: string }
  speedup_factor: number
}

export interface CheckpointsAudit {
  root_checkpoints: Record<string, CheckpointItem>
  v4_checkpoints: Record<string, CheckpointItem>
  manifest_verified: boolean
  manifest_details?: any
}

export interface TrainingEpoch {
  epoch: number
  sec: number
  loss_G: number
  bce: number
  ber_link: number
  ber5: number
  ks_p: number
  Sc: number
  n_pass: number
  gate: string
}

export interface EvaluationLinkSNR {
  snr_db: number
  mf_ber: number
  field_ber: number
  fer: number
  bits_tested: number
  frames_tested: number
  field_ci95?: number
  fer_ci95?: number
  ci95?: number
}

export interface EvaluationReport {
  has_report: boolean
  stealth: {
    ks_p: number
    kurt: number
    entropy: number
    adv_acc: number
    n_pass: number
    Sc: number
  }
  link_snrs: EvaluationLinkSNR[]
  gate_verdict: string
  summary_md?: string
}

export type AnomalyState = 'NOMINAL' | 'WATCH' | 'ANOMALY' | 'UNKNOWN'

export interface AnomalyDomain {
  key: string
  label: string
  unit: string
  expectation: string
  baseline: number | null
  observed: number | null
  delta: number | null
  drift: number | null
  tolerance: number
  tolerance_mode: 'abs' | 'rel'
  ew_deviation: number | null
  passed: boolean | null
  state: AnomalyState
}

export interface OperationalAnomaly {
  key: string
  label: string
  observed: number | null
  baseline: string
  unit: string
  state: AnomalyState
  detail: string
  threshold: Record<string, number>
}

export interface ModelTelemetry {
  subsystem: string
  checkpoint: string
  checkpoint_path: string | null
  sha256: string | null
  sha256_short: string | null
  size_bytes: number | null
  generation: string | null
  exported_from: string | null
  epoch: number | null
  manifest_verified: boolean
  inference_device: string
  recommended_device: string
  mps_available: boolean
  pytorch_version: string
  platform: string
  stealth: {
    ks_p?: number
    kurt?: number
    entropy?: number
    adv_acc?: number
    n_pass?: number
    Sc?: number
  }
  adversary_acc_pct: number | null
  gate_verdict: string | null
  n_pass: number | null
  link_snrs: EvaluationLinkSNR[]
  documented_processing_gain_db: number
}

export interface AnomalyReport {
  generated_at: string
  summary: { state: AnomalyState; counts: Record<string, number>; total: number }
  provenance: 'LIVE_COMPUTED' | 'BASELINE_REPLAY'
  baseline_source: string
  model: ModelTelemetry
  domains: AnomalyDomain[]
  operational: OperationalAnomaly[]
  ew: {
    n_frames: number | null
    Sc: number | null
    grade: string | null
    n_pass: number | null
    error: string | null
    disclaimer: string
  }
}

// ---------------------------------------------------------------------------
// Waveform Lab — LPI-CGAN vs. conventional (non-LPI) reference
// ---------------------------------------------------------------------------
export interface WaveformDomain {
  key: string
  label: string
  unit: string
  criterion: string
  value: number | null
  passed: boolean
}

export interface WaveformSample {
  sample: number
  i: number
  q: number
}

export interface ScatterPoint {
  i: number
  q: number
}

export interface SpectrumPoint {
  freq_khz: number
  power_db: number
}

export type WaveformClass =
  | 'INDISTINGUISHABLE_FROM_NOISE'
  | 'PARTIALLY_MASKED'
  | 'DETECTABLE'
  | 'UNAVAILABLE'

export interface WaveformTrack {
  id: 'lpi' | 'conventional'
  label: string
  source: string
  spec?: string
  available: boolean
  unavailable_reason?: string | null
  waveform: WaveformSample[]
  constellation: ScatterPoint[]
  symbol_centers: ScatterPoint[]
  spectrum: SpectrumPoint[]
  sample_count?: number
  frame_shape?: [number, number, number]
  domains: WaveformDomain[]
  n_pass: number
  n_domains: number
  stealth_score: number | null
  Sc?: number
  grade?: string | null
  classification: WaveformClass
}

export interface ContrastRow {
  key: string
  label: string
  criterion: string
  unit: string
  lpi: number | null
  conventional: number | null
  lpi_pass: boolean
  conventional_pass: boolean
  flips: boolean
}

export interface WaveformComparison {
  generated_at: string
  provenance: 'LIVE_COMPUTED' | 'PARTIAL'
  frame: {
    n_bits: number
    frame_len: number
    out_len: number
    pilot_len: number
    total_len: number
    z_dim: number
    fs_hz: number
    dither_eps: number
    processing_gain_db: number
  }
  comparison_basis: string
  tracks: { lpi: WaveformTrack; conventional: WaveformTrack }
  contrast: ContrastRow[]
  verdict: {
    lpi_pass: number | null
    conventional_pass: number
    domains_flipped: number
    headline: string
  }
  disclaimer: string
}

export interface SignalSample {
  source: string
  checkpoint?: string
  device?: string
  processing_gain_db?: number
  constellation: Array<{ i: number; q: number }>
  spectrum: Array<{ freq_khz: number; power_db: number }>
  waveform: Array<{ sample: number; i: number; q: number; mag: number }>
  fallback_active?: boolean
  footnote?: string | null
}

export interface EnvironmentMetadata {
  platform: string
  python_version: string
  processor: string
  machine: string
  is_apple_silicon: boolean
  pytorch_version: string
  mps_available: boolean
  cuda_available: boolean
  recommended_device: string
  operational_notes: string
  active_backend?: string
  active_inference_backend?: string
  thread_count?: number
  fallback_active?: boolean
  mps_built?: boolean
}

export interface LocalOutboxItem {
  client_idempotency_key: string
  sender_endpoint_id: string
  recipient_endpoint_id: string
  payload: string
  message_type?: string
  priority?: number
  expires_in_seconds?: number
  created_at: string
  sync_status: 'PENDING_LOCAL' | 'SYNCED' | 'FAILED_SYNC'
  error_message?: string
}

export interface SDRHardwareStatus {
  driver_installed: boolean
  driver_version: string
  device_connected: boolean
  device_count: number
  devices: string[]
  operating_mode: string
  center_freq_hz: number
  sample_rate_sps: number
  decimation_ratio: number
  master_clock_hz: number
  tx_gain_db: number
  rx_gain_db: number
}

export interface WorkstationOverview {
  system_state: string
  system_name: string
  system_title: string
  timestamp: string
  sdr_hardware: SDRHardwareStatus
  model_status: {
    loaded: boolean
    model_name: string
    generation: string
    device: string
    spreading_gain_db: number
    parameters_count: number
  }
  crypto_status: {
    algorithm: string
    key_size_bits: number
    fec: string
    mac_tag_bits: number
    authentication: string
  }
  stealth_summary: {
    ks_p: number
    kurtosis: number
    entropy: number
    adv_acc: number
    spreading_gain_db: number
    gate_verdict: string
  }
  recent_events: Array<{ timestamp: string; level: string; source: string; message: string }>
  active_warnings: string[]
}

export interface TransmitterPreparation {
  raw_text: string
  raw_bytes_count: number
  message_type: string
  crypto_envelope: {
    scheme: string
    nonce_hex: string
    tag_hex: string
    envelope_bytes: number
  }
  error_correction: {
    scheme: string
    data_per_block: number
    codeword_per_block: number
    parity_per_block: number
    error_correcting_capacity_symbols: number
    total_blocks: number
    total_codeword_bytes: number
    parity_overhead_bytes: number
  }
  rf_budget: {
    carrier_freq_hz: number
    sample_rate_sps: number
    preamble_samples: number
    payload_samples_per_block: number
    total_frame_samples: number
    burst_airtime_ms: number
    spreading_gain_db: number
    target_snr_db: number
    signal_psd_dbm: number
    thermal_noise_floor_dbm: number
    probability_detection_pd: number
    probability_false_alarm_pfa: number
  }
  wire_hex_memory_map: string[]
  is_valid: boolean
}

export interface ReceiverDSPStage {
  stage_id: number
  name: string
  state: string
  input_spec: string
  output_spec: string
  duration_ms: number
  result: string
  notes: string
}

export interface ReceiverDSPPipelineResult {
  recovery_status: string
  overall_status?: string
  error?: string
  details?: string
  mode: string
  target_snr_db: number
  recovered_plaintext: string
  total_stages: number
  total_duration_ms: number
  bit_error_rate_ber: number
  frame_error_rate_fer: number
  signed_ack_receipt: string
  stages: ReceiverDSPStage[]
}

export interface ChannelSimulationResult {
  channel_parameters: {
    target_snr_db: number
    measured_snr_db: number
    carrier_frequency_offset_hz: number
    phase_offset_deg: number
    multipath_enabled: boolean
    noise_variance: number
    signal_power: number
  }
  clean_waveform_preview: Array<{ sample: number; i: number; q: number; mag: number }>
  distorted_waveform_preview: Array<{ sample: number; i: number; q: number; mag: number }>
  clean_constellation: Array<{ i: number; q: number }>
  impaired_constellation: Array<{ i: number; q: number }>
  impaired_spectrum: Array<{ freq_khz: number; power_db: number }>
}

export interface SignalIntelligenceData {
  status?: string
  warning?: string
  fallback_source?: string
  time_domain: Array<{ sample: number; time_us?: number; i: number; q: number; mag: number }>
  frequency_spectrum: Array<{ freq_khz: number; rf_freq_mhz?: number; power_db: number }>
  constellation: Array<{ sample?: number; i: number; q: number }>
  autocorrelation: Array<{ lag: number; correlation: number }>
  spectrogram: Array<{ time_step: number; time_ms?: number; freq_bin: number; freq_khz?: number; intensity: number }>
  statistics: {
    peak_amplitude: number
    rms_amplitude: number
    papr_db: number
    spectral_kurtosis?: number
    spectral_entropy?: number
    ks_p_value?: number
    circularity?: number
    sample_rate_sps: number
    center_freq_hz: number
    rbw_hz: number
    vbw_hz: number
    fft_size: number
    window: string
    calibration: string
    samples_processed?: number
  }
  provenance: {
    source: string
    source_label?: string
    model_checkpoint?: string
    is_calibrated_rf?: boolean
    calibration_badge?: string
    units?: {
      power: string
      amplitude: string
      time: string
      frequency: string
    }
    sample_rate_sps: number
    center_freq_hz?: number
    fft_size?: number
    window?: string
    rbw_hz?: number
    vbw_hz?: number
    timestamp?: string
    file_metadata?: any
    calibrated?: boolean
  }
}

export interface GlossaryItem {
  term: string
  category: string
  definition: string
  relevance: string
}

export interface HelpDocSection {
  heading: string
  content: string
}

export interface HelpDocumentation {
  getting_started: {
    title: string
    sections: HelpDocSection[]
  }
  communication_pipeline: {
    title: string
    sections: HelpDocSection[]
  }
  signal_visualisations: {
    title: string
    sections: HelpDocSection[]
  }
  diagnostics_faq: {
    title: string
    faqs: Array<{ q: string; a: string }>
  }
}

export interface SystemDiagnosticsData {
  backend_status: string
  api_version: string
  server_time: string
  uptime_seconds: number
  os_platform: string
  python_version: string
  pytorch_backend: {
    version: string
    mps_available: boolean
    cuda_available: boolean
    active_device: string
  }
  sdr_hardware: SDRHardwareStatus
  database: {
    db_file: string
    status: string
    mode: string
  }
  diagnostics_summary: string
}

export interface StationHealthMetadata {
  status: string
  service: string
  version: string
  station_id: string
  station_name: string
  db_path: string
  port: number
  peer_url?: string
  worker_status?: string
  transport_mode?: string
}

export interface KeyringInfo {
  station_id?: string
  endpoint_id?: string
  station_name?: string
  display_name?: string
  public_key_pqc: string | null
  public_key_x25519: string | null
  fingerprint_pqc?: string
  fingerprint_x25519?: string
  pqc_fingerprint?: string
  x25519_fingerprint?: string
  keyring_path?: string
  keyring_status?: string
  is_zeroized?: boolean
  peer_keys?: Record<string, { public_key_pqc: string | null; public_key_x25519: string | null; status: string }>
}

export interface RotateKeysResponse {
  status: string
  station_id?: string
  endpoint_id?: string
  public_key_pqc: string
  public_key_x25519: string
  pqc_fingerprint?: string
  x25519_fingerprint?: string
  rotated_at: string
  audit_log_id?: string
}

export interface TamperTestResponse {
  status?: string
  detail?: string
  rejected_with_status?: number
  audit_action?: string
  verified?: boolean
  test_id?: string
  target?: string
  target_url?: string
  injected_fault?: string
  peer_http_status?: number
  peer_response_code?: string
  tamper_detected?: boolean
  audit_event_logged?: boolean
}

export interface PQCKeyExchangeParams {
  pqc_scheme: string
  kem_algorithm: string
  classical_algorithm: string
  kdf: string
  symmetric_cipher: string
  ciphertext_size_bytes: number
  aad_spec: string
}

// ---------------------------------------------------------------------------
// Multi-Hop Ad-Hoc Mesh Routing & Relay Protocol (Phase 08)
// ---------------------------------------------------------------------------
export interface MeshNode {
  id: string
  display_name: string
  node_type: string
  status: string
  battery_percentage: number
  storage_used_pct: number
  queue_depth: number
  position: [number, number, number]
  is_approved: boolean
  failsafe_cutoff_active: boolean
  sector: string
}

export interface MeshLink {
  source: string
  target: string
  distance_km: number
  max_range_km: number
  rf_tier: 'GROUND_GROUND' | 'GROUND_UAV' | 'UAV_UAV'
  latency_ms: number
  is_active_route: boolean
  is_broken?: boolean
}

export interface MeshActiveRoute {
  source: string
  destination: string
  path: string[]
  total_hops: number
  estimated_latency_ms: number
  route_status: 'OPTIMAL' | 'SUBOPTIMAL' | 'NO_ROUTE'
}

export interface MeshTopologyData {
  nodes: MeshNode[]
  links: MeshLink[]
  active_route: MeshActiveRoute
}

export interface MeshScenarioResponse {
  scenario: string
  previous_path: string[]
  new_path: string[]
  reroute_event: string
  convergence_latency_ms: number
  status: string
}

// ---------------------------------------------------------------------------
// Advanced RF Field Tools, Live Waterfall & Link Budget (Phase 09)
// ---------------------------------------------------------------------------
export interface TacticalBandPreset {
  name: string
  freq_mhz: number
  tx_power_dbm: number
  tx_gain_dbi: number
  rx_gain_dbi: number
  rx_sensitivity_dbm: number
  description: string
}

export interface LinkBudgetResult {
  distance_km: number
  freq_mhz: number
  fspl_db: number
  eirp_dbm: number
  rx_power_dbm: number
  thermal_noise_dbm: number
  snr_db: number
  rx_sensitivity_dbm: number
  link_margin_db: number
  status: 'OPTIMAL' | 'MARGINAL' | 'FADE_THREAT'
  status_color: string
  status_desc: string
  presets?: Record<string, TacticalBandPreset>
}

export interface LinkBudgetRequest {
  preset?: string
  distance_km?: number
  freq_mhz?: number
  tx_power_dbm?: number
  tx_gain_dbi?: number
  rx_gain_dbi?: number
  cable_loss_db?: number
  rx_sensitivity_dbm?: number
}




