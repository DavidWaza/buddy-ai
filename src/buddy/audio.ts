/**
 * Browser audio: microphone level (Web Audio), spoken replies
 * (speechSynthesis) and live transcripts (SpeechRecognition, Chrome/Edge).
 * Each class has a static `supported()` so callers can fall back cleanly.
 */

import type { MicInput, Recognizer, SpeechCallbacks, SpeechOutput, VoiceStyle } from './voice'

function percentile(values: number[], p: number): number {
  const sorted = [...values].sort((a, b) => a - b)
  return sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))] ?? 0
}

/**
 * Loudness above an adaptive noise floor (a low percentile of the last few
 * seconds), so a noisy room still reads as silence.
 */
export class BrowserMic implements MicInput {
  static readonly HISTORY_FRAMES = 240 // ~4 s at 60 fps
  static readonly HEADROOM_DB = 5
  static readonly RANGE_DB = 25

  static supported(): boolean {
    return typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia
  }

  private ctx: AudioContext | null = null
  private stream: MediaStream | null = null
  private source: MediaStreamAudioSourceNode | null = null
  private analyser: AnalyserNode | null = null
  private readonly buffer = new Float32Array(1024)
  private history: number[] = []
  private token = 0

  async start(): Promise<void> {
    const token = ++this.token
    // Create/resume the context before awaiting, while still inside the tap.
    this.ctx ??= new AudioContext()
    void this.ctx.resume()
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    })
    if (token !== this.token) {
      stream.getTracks().forEach((t) => t.stop())
      return
    }
    this.stream = stream
    this.source = this.ctx.createMediaStreamSource(stream)
    this.analyser = this.ctx.createAnalyser()
    this.analyser.fftSize = this.buffer.length
    this.source.connect(this.analyser)
    this.history = []
  }

  stop(): void {
    this.token++
    this.source?.disconnect()
    this.stream?.getTracks().forEach((t) => t.stop())
    this.stream = this.source = this.analyser = null
  }

  readLevel(): number {
    if (!this.analyser) return 0
    this.analyser.getFloatTimeDomainData(this.buffer)
    let sum = 0
    for (const v of this.buffer) sum += v * v
    const db = 20 * Math.log10(Math.sqrt(sum / this.buffer.length) + 1e-9)
    if (db > -90) {
      this.history.push(db)
      if (this.history.length > BrowserMic.HISTORY_FRAMES) this.history.shift()
    }
    if (this.history.length < 20) return 0
    const floor = percentile(this.history, 0.2)
    return Math.min(1, Math.max(0, (db - floor - BrowserMic.HEADROOM_DB) / BrowserMic.RANGE_DB))
  }
}

export class BrowserSpeaker implements SpeechOutput {
  static supported(): boolean {
    return typeof window !== 'undefined' && 'speechSynthesis' in window
  }

  // Held so the browser can't garbage-collect it mid-sentence (drops events in Chrome).
  private current: SpeechSynthesisUtterance | null = null

  constructor() {
    speechSynthesis.getVoices() // start loading the voice list early
  }

  /** Call from a tap: iOS only allows speech once it was started by a gesture. */
  unlock(): void {
    if (!speechSynthesis.speaking) speechSynthesis.speak(new SpeechSynthesisUtterance(''))
  }

  speak(text: string, style: VoiceStyle, callbacks: SpeechCallbacks): void {
    speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    const voice = pickVoice(style.voiceIndex)
    if (voice) {
      utterance.voice = voice
      utterance.lang = voice.lang
    }
    utterance.rate = style.rate
    utterance.pitch = style.pitch
    utterance.onboundary = (e) => {
      if (e.name === 'word' || !e.name) callbacks.onBoundary(e.charIndex)
    }
    utterance.onend = () => callbacks.onEnd()
    utterance.onerror = (e) => {
      if (e.error !== 'interrupted' && e.error !== 'canceled') callbacks.onError()
    }
    this.current = utterance
    speechSynthesis.speak(utterance)
  }

  stop(): void {
    this.current = null
    speechSynthesis.cancel()
  }
}

/** English voices, most natural-sounding first; models pick by index. */
function pickVoice(index: number): SpeechSynthesisVoice | undefined {
  const all = speechSynthesis.getVoices()
  const english = all.filter((v) => v.lang.toLowerCase().startsWith('en'))
  const pool = english.length ? english : all
  const score = (v: SpeechSynthesisVoice) =>
    (/natural|neural|online/i.test(v.name) ? 2 : 0) + (v.localService ? 1 : 0)
  const ranked = [...pool].sort((a, b) => score(b) - score(a))
  return ranked.length ? ranked[index % ranked.length] : undefined
}

interface RecognitionResultList {
  length: number
  [index: number]: { [index: number]: { transcript: string } | undefined } | undefined
}

interface RecognitionInstance {
  continuous: boolean
  interimResults: boolean
  lang: string
  onresult: ((event: { results: RecognitionResultList }) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
  start(): void
  abort(): void
}

type RecognitionCtor = new () => RecognitionInstance

function recognitionCtor(): RecognitionCtor | undefined {
  if (typeof window === 'undefined') return undefined
  const w = window as unknown as {
    SpeechRecognition?: RecognitionCtor
    webkitSpeechRecognition?: RecognitionCtor
  }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition
}

export class BrowserRecognizer implements Recognizer {
  static supported(): boolean {
    return !!recognitionCtor()
  }

  private rec: RecognitionInstance | null = null
  private active = false

  start(onText: (text: string) => void): void {
    const Ctor = recognitionCtor()
    if (!Ctor) return
    this.stop()
    const rec = new Ctor()
    rec.continuous = true
    rec.interimResults = true
    rec.lang = navigator.language || 'en-US'
    rec.onresult = (event) => {
      let text = ''
      for (let i = 0; i < event.results.length; i++) text += event.results[i]?.[0]?.transcript ?? ''
      onText(text.trim())
    }
    rec.onerror = (event) => {
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed')
        this.active = false
    }
    rec.onend = () => {
      // Chrome ends sessions after a quiet spell; keep going while listening.
      if (this.active && this.rec === rec) {
        try {
          rec.start()
        } catch {
          this.active = false
        }
      }
    }
    this.rec = rec
    this.active = true
    try {
      rec.start()
    } catch {
      this.active = false
    }
  }

  stop(): void {
    this.active = false
    this.rec?.abort()
    this.rec = null
  }
}
