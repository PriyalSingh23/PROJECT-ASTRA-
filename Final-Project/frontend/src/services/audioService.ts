/**
 * Tactical Web Audio sound synthesis service.
 * Synthesizes RF squelch bursts on link degradation and clean chimes on link restoration.
 * Designed with lazy AudioContext initialization upon user interaction.
 */
class AudioService {
  private ctx: AudioContext | null = null
  private isMuted: boolean = typeof window !== 'undefined' ? localStorage.getItem('shadowcomm_audio_muted') === 'true' : false

  private getContext(): AudioContext | null {
    if (typeof window === 'undefined') return null
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
      if (AudioCtx) {
        this.ctx = new AudioCtx()
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume().catch(() => {})
    }
    return this.ctx
  }

  playSquelch(): void {
    if (this.isMuted) return
    const ctx = this.getContext()
    if (!ctx) return

    try {
      // Synthesize 60ms bandpass white noise burst
      const bufferSize = Math.floor(ctx.sampleRate * 0.06)
      const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate)
      const output = buffer.getChannelData(0)
      for (let i = 0; i < bufferSize; i++) {
        output[i] = (Math.random() * 2 - 1) * Math.exp(-i / (bufferSize * 0.5))
      }
      const whiteNoise = ctx.createBufferSource()
      whiteNoise.buffer = buffer

      const filter = ctx.createBiquadFilter()
      filter.type = 'bandpass'
      filter.frequency.value = 1200
      filter.Q.value = 3.0

      const gain = ctx.createGain()
      gain.gain.setValueAtTime(0.08, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.06)

      whiteNoise.connect(filter)
      filter.connect(gain)
      gain.connect(ctx.destination)
      whiteNoise.start()
    } catch {
      // Graceful fallback if Web Audio is blocked or unsupported
    }
  }

  playRestoreChime(): void {
    if (this.isMuted) return
    const ctx = this.getContext()
    if (!ctx) return

    try {
      // Synthesize pleasant 2-tone clean link chime (880Hz -> 1760Hz)
      const now = ctx.currentTime
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'sine'
      osc.frequency.setValueAtTime(880, now)
      osc.frequency.setValueAtTime(1760, now + 0.08)

      gain.gain.setValueAtTime(0.06, now)
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25)

      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.start(now)
      osc.stop(now + 0.25)
    } catch {
      // Graceful fallback
    }
  }

  toggleMute(): boolean {
    this.isMuted = !this.isMuted
    if (typeof window !== 'undefined') {
      localStorage.setItem('shadowcomm_audio_muted', String(this.isMuted))
    }
    return this.isMuted
  }

  getMuted(): boolean {
    return this.isMuted
  }
}

export const audioService = new AudioService()
