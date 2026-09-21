/**
 * Conversation state machine: idle -> listening -> thinking -> speaking -> idle.
 *
 * Audio comes in through small interfaces (mic, speaker, recognizer) so the
 * browser implementations in `audio.ts` can be swapped for fakes in tests.
 * Anything that is missing or fails is replaced by a simulation, so the
 * buddy always has something believable to react to.
 */

export type Mode = 'idle' | 'listening' | 'thinking' | 'speaking'
export const MODES: readonly Mode[] = ['idle', 'listening', 'thinking', 'speaking']

export type Rng = () => number

/** Small deterministic PRNG (mulberry32) for reproducible tests. */
export function seededRng(seed: number): Rng {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export const uniform = (rng: Rng, lo: number, hi: number) => lo + (hi - lo) * rng()

/** Frame-rate independent exponential smoothing. */
export function approach(current: number, target: number, rate: number, dt: number): number {
  return current + (target - current) * (1 - Math.exp(-rate * dt))
}

export function countSyllables(word: string): number {
  const w = word.toLowerCase()
  const groups = w.match(/[aeiouy]+/g) ?? []
  const silentE = w.replace(/[.,!?;:'"]+$/, '').endsWith('e') && groups.length > 1
  return Math.max(1, groups.length - (silentE ? 1 : 0))
}

export const NO_SPEECH_REPLIES = [
  "Hmm, I didn't quite catch that, {name}. Could you say it again?",
  "I'm here and listening, {name}. Whenever you're ready, just speak up.",
]
export const SHORT_REPLIES = [
  'Got it, {name}! Thanks for letting me know.',
  'Okay, understood. Is there anything else on your mind?',
  'Nice! I hear you loud and clear.',
]
export const LONG_REPLIES = [
  'Thanks for sharing all of that, {name}. That sounds really thoughtful. Tell me more whenever you like.',
  "I hear you. That's a lot to think about, and you explained it really well.",
  "Great point, {name}. I love where you're going with this. Let's keep talking.",
]
/** Used when speech recognition caught the words, so the buddy can quote them. */
export const HEARD_REPLIES = [
  'I heard you say, "{snippet}". Thanks for sharing that, {name}!',
  '"{snippet}". Got it, {name}. Tell me more whenever you like.',
]

export interface ReplyContext {
  name: string
  talkTime: number
  transcript: string
  last?: string
}

/** Pick a generic reply based on how much was said (and what, when known). */
export function chooseReply(rng: Rng, ctx: ReplyContext): { template: string; text: string } {
  const words = ctx.transcript.split(/\s+/).filter(Boolean)
  let pool: string[]
  if (words.length >= 3 && rng() < 0.6) pool = HEARD_REPLIES
  else if (words.length === 0 && ctx.talkTime < 0.3) pool = NO_SPEECH_REPLIES
  else if (words.length > 0 ? words.length <= 4 : ctx.talkTime < 2) pool = SHORT_REPLIES
  else pool = LONG_REPLIES

  const options = pool.length > 1 ? pool.filter((r) => r !== ctx.last) : pool
  const template = options[Math.floor(rng() * options.length)] ?? pool[0]!
  const snippet =
    words
      .slice(0, 6)
      .join(' ')
      .replace(/[.,!?;:]+$/, '') + (words.length > 6 ? '...' : '')
  const text = template.replaceAll('{name}', ctx.name).replaceAll('{snippet}', snippet)
  return { template, text }
}

/** Fakes a microphone level: bursts of talking separated by pauses. */
export class MicSimulator {
  level = 0
  private talking = false
  private segmentLeft: number
  private retargetIn = 0
  private target = 0

  constructor(private readonly rng: Rng) {
    this.segmentLeft = uniform(rng, 0.3, 0.6)
  }

  step(dt: number): number {
    const rng = this.rng
    this.segmentLeft -= dt
    if (this.segmentLeft <= 0) {
      this.talking = !this.talking
      this.segmentLeft = this.talking ? uniform(rng, 0.7, 2.2) : uniform(rng, 0.25, 0.9)
    }
    this.retargetIn -= dt
    if (this.retargetIn <= 0) {
      this.retargetIn = uniform(rng, 0.05, 0.15)
      this.target = this.talking ? uniform(rng, 0.35, 1) : uniform(rng, 0, 0.05)
    }
    this.level = approach(this.level, this.target, 20, dt)
    return this.level
  }
}

export interface TimedWord {
  text: string
  charIndex: number
  start: number
  end: number
  syllables: number
  peak: number
}

/**
 * Word-by-word schedule for a reply. Drives the captions and a
 * syllable-shaped mouth level; resynced from the voice's word boundaries.
 */
export class SpeechTimeline {
  readonly words: TimedWord[] = []
  readonly duration: number
  elapsed = 0

  constructor(
    readonly text: string,
    private readonly rng: Rng,
    rate = 1,
  ) {
    let t = 0.3
    for (const match of text.matchAll(/\S+/g)) {
      const raw = match[0]
      const syllables = countSyllables(raw)
      const duration = (0.1 + 0.16 * syllables) / rate
      this.words.push({
        text: raw,
        charIndex: match.index,
        start: t,
        end: t + duration,
        syllables,
        peak: uniform(rng, 0.6, 1),
      })
      t += duration + 0.05 / rate
      const last = raw.at(-1) ?? ''
      if (',;:'.includes(last)) t += 0.22 / rate
      else if ('.!?'.includes(last)) t += 0.45 / rate
    }
    this.duration = t + 0.2
  }

  get done(): boolean {
    return this.elapsed >= this.duration
  }

  step(dt: number): number {
    this.elapsed += dt
    for (const w of this.words) {
      if (w.start <= this.elapsed && this.elapsed < w.end) {
        const phase = (((this.elapsed - w.start) / (w.end - w.start)) * w.syllables) % 1
        return w.peak * Math.sin(Math.PI * phase) ** 0.6 * uniform(this.rng, 0.85, 1)
      }
    }
    return 0
  }

  /** The voice just started the word at `charIndex`: snap the schedule to it. */
  syncToChar(charIndex: number): void {
    const word = this.words.findLast((w) => w.charIndex <= charIndex)
    if (word && Math.abs(this.elapsed - word.start) > 0.12) this.elapsed = word.start
  }

  finish(): void {
    this.elapsed = Math.max(this.elapsed, this.duration)
  }

  wordProgress(): number[] {
    return this.words.map((w) =>
      this.elapsed <= w.start
        ? 0
        : this.elapsed >= w.end
          ? 1
          : (this.elapsed - w.start) / (w.end - w.start),
    )
  }
}

export interface MicInput {
  start(): Promise<void>
  stop(): void
  /** Current loudness in [0, 1]; call once per frame. */
  readLevel(): number
}

export interface VoiceStyle {
  voiceIndex: number
  rate: number
  pitch: number
}

export interface SpeechCallbacks {
  onBoundary(charIndex: number): void
  onEnd(): void
  onError(): void
}

export interface SpeechOutput {
  speak(text: string, style: VoiceStyle, callbacks: SpeechCallbacks): void
  stop(): void
}

export interface Recognizer {
  start(onText: (text: string) => void): void
  stop(): void
}

export interface ConversationOptions {
  name?: string
  rng?: Rng
  mic?: MicInput | null
  speaker?: SpeechOutput | null
  recognizer?: Recognizer | null
}

type TtsState = 'none' | 'playing' | 'ended' | 'failed'

export class Conversation {
  static readonly THINK_SECONDS: [number, number] = [0.9, 1.6]
  static readonly SPEECH_LEVEL = 0.28 // mic level that counts as talking
  static readonly END_OF_TURN_SILENCE = 1.5
  static readonly NO_SPEECH_TIMEOUT = 12
  static readonly VOICE_GRACE = 6 // extra seconds to wait for a slow voice

  mode: Mode = 'idle'
  modeTime = 0
  level = 0
  transcript = ''
  speech: SpeechTimeline | null = null
  voice: VoiceStyle = { voiceIndex: 0, rate: 1, pitch: 1 }
  name: string

  private readonly rng: Rng
  private mic: MicInput | null
  private speaker: SpeechOutput | null
  private readonly recognizer: Recognizer | null
  private usingLiveMic = false
  private liveTime = 0
  private sim: MicSimulator | null = null
  private talkTime = 0
  private silence = 0
  private thinkLeft = 0
  private replyText = ''
  private lastTemplate: string | undefined
  private tts: TtsState = 'none'
  private session = 0
  private readonly modeListeners: ((mode: Mode) => void)[] = []
  private readonly noticeListeners: ((message: string) => void)[] = []

  constructor(options: ConversationOptions = {}) {
    this.name = options.name ?? 'friend'
    this.rng = options.rng ?? Math.random
    this.mic = options.mic ?? null
    this.speaker = options.speaker ?? null
    this.recognizer = options.recognizer ?? null
  }

  get liveMic(): boolean {
    return this.usingLiveMic
  }

  onModeChanged(callback: (mode: Mode) => void): void {
    this.modeListeners.push(callback)
  }

  onNotice(callback: (message: string) => void): void {
    this.noticeListeners.push(callback)
  }

  /** Mic tap: start listening, or finish the turn if already listening. */
  toggleMic(): void {
    this.setMode(this.mode === 'listening' ? 'thinking' : 'listening')
  }

  cancel(): void {
    this.setMode('idle')
  }

  step(dt: number): void {
    this.modeTime += dt
    let raw = 0
    if (this.mode === 'listening') {
      if (this.usingLiveMic && this.mic) raw = this.mic.readLevel()
      else if (!this.mic && this.sim) raw = this.sim.step(dt) // no mic at all: simulate
      this.trackTurn(raw, dt)
    } else if (this.mode === 'thinking') {
      raw = 0.12 + 0.06 * Math.sin(this.modeTime * 6)
      this.thinkLeft -= dt
      if (this.thinkLeft <= 0) this.setMode('speaking')
    } else if (this.mode === 'speaking' && this.speech) {
      const s = this.speech
      if (this.tts === 'ended') {
        s.finish()
        this.setMode('idle')
      } else {
        raw = s.step(dt)
        const overtime = s.elapsed - s.duration
        if (this.tts === 'playing' ? overtime > Conversation.VOICE_GRACE : overtime >= 0) {
          this.setMode('idle')
        }
      }
    }
    this.level = approach(this.level, raw, 14, dt)
  }

  private trackTurn(raw: number, dt: number): void {
    if (raw > Conversation.SPEECH_LEVEL) {
      this.talkTime += dt
      this.silence = 0
    } else {
      this.silence += dt
    }
    if (!this.usingLiveMic) return
    this.liveTime += dt
    const finishedTalking = this.talkTime > 0.5 && this.silence > Conversation.END_OF_TURN_SILENCE
    const gaveUp = this.talkTime < 0.3 && this.liveTime > Conversation.NO_SPEECH_TIMEOUT
    if (finishedTalking || gaveUp) this.setMode('thinking')
  }

  private setMode(mode: Mode): void {
    if (mode === this.mode) return
    this.leave(this.mode)
    this.mode = mode
    this.modeTime = 0
    if (mode === 'listening') this.startListening()
    else if (mode === 'thinking') this.startThinking()
    else if (mode === 'speaking') this.startSpeaking()
    for (const cb of this.modeListeners) cb(mode)
  }

  private leave(mode: Mode): void {
    if (mode === 'listening') {
      this.mic?.stop()
      this.recognizer?.stop()
      this.usingLiveMic = false
    } else if (mode === 'speaking' && this.tts === 'playing') {
      this.speaker?.stop()
      this.tts = 'none'
    }
  }

  private startListening(): void {
    const session = ++this.session
    this.speech = null
    this.transcript = ''
    this.talkTime = this.silence = this.liveTime = 0
    this.sim = new MicSimulator(this.rng)
    const mic = this.mic
    if (mic) {
      mic
        .start()
        .then(() => {
          if (session === this.session && this.mode === 'listening') this.usingLiveMic = true
          else mic.stop()
        })
        .catch(() => {
          if (this.mic !== mic) return
          this.mic = null
          this.notice('Microphone blocked, simulating your voice')
        })
    }
    this.recognizer?.start((text) => {
      if (session === this.session) this.transcript = text
    })
  }

  private startThinking(): void {
    this.thinkLeft = uniform(this.rng, ...Conversation.THINK_SECONDS)
    const reply = chooseReply(this.rng, {
      name: this.name,
      talkTime: this.talkTime,
      transcript: this.transcript,
      last: this.lastTemplate,
    })
    this.lastTemplate = reply.template
    this.replyText = reply.text
  }

  private startSpeaking(): void {
    const session = ++this.session
    this.speech = new SpeechTimeline(this.replyText, this.rng, this.voice.rate)
    this.tts = 'none'
    if (!this.speaker) return
    this.tts = 'playing'
    const alive = () => session === this.session && this.mode === 'speaking'
    this.speaker.speak(this.replyText, this.voice, {
      onBoundary: (charIndex) => {
        if (alive()) this.speech?.syncToChar(charIndex)
      },
      onEnd: () => {
        if (!alive()) return
        // An "end" before anything could be heard means the voice never played.
        if ((this.speech?.elapsed ?? 0) < 0.3) this.voiceFailed()
        else this.tts = 'ended'
      },
      onError: () => {
        if (alive()) this.voiceFailed()
      },
    })
  }

  private voiceFailed(): void {
    this.tts = 'failed'
    this.speaker = null
    this.notice('Voice unavailable in this browser, showing captions only')
  }

  private notice(message: string): void {
    for (const cb of this.noticeListeners) cb(message)
  }
}
