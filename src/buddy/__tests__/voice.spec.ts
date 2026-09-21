import { describe, expect, it } from 'vitest'
import {
  chooseReply,
  Conversation,
  countSyllables,
  HEARD_REPLIES,
  LONG_REPLIES,
  NO_SPEECH_REPLIES,
  SHORT_REPLIES,
  seededRng,
  type MicInput,
  type Mode,
  type SpeechCallbacks,
  type SpeechOutput,
} from '../voice'

const DT = 1 / 60

function run(conv: Conversation, seconds: number) {
  for (let i = 0; i < Math.round(seconds / DT); i++) conv.step(DT)
}

async function flush() {
  await new Promise((resolve) => setTimeout(resolve, 0))
}

class FakeMic implements MicInput {
  level = 0
  started = 0
  stopped = 0
  async start() {
    this.started++
  }
  stop() {
    this.stopped++
  }
  readLevel() {
    return this.level
  }
}

class FakeSpeaker implements SpeechOutput {
  spoken: string[] = []
  callbacks: SpeechCallbacks | null = null
  stopped = 0
  speak(text: string, _style: unknown, callbacks: SpeechCallbacks) {
    this.spoken.push(text)
    this.callbacks = callbacks
  }
  stop() {
    this.stopped++
  }
}

const fill = (pool: string[], name: string) => pool.map((r) => r.replaceAll('{name}', name))

describe('Conversation without audio devices', () => {
  it('runs a full turn and returns to idle', () => {
    const conv = new Conversation({ name: 'Ada', rng: seededRng(1) })
    const seen: Mode[] = []
    conv.onModeChanged((m) => seen.push(m))
    conv.toggleMic()
    run(conv, 1)
    expect(conv.mode).toBe('listening')
    conv.toggleMic()
    run(conv, 30)
    expect(seen).toEqual(['listening', 'thinking', 'speaking', 'idle'])
    expect(conv.speech?.text).not.toContain('{name}')
  })

  it('lets the mic interrupt speaking, and cancel resets', () => {
    const conv = new Conversation({ rng: seededRng(2) })
    conv.toggleMic()
    conv.toggleMic()
    run(conv, 2)
    expect(conv.mode).toBe('speaking')
    conv.toggleMic()
    expect(conv.mode).toBe('listening')
    conv.cancel()
    expect(conv.mode).toBe('idle')
  })

  it('keeps the level within 0..1', () => {
    const conv = new Conversation({ rng: seededRng(3) })
    conv.toggleMic()
    for (let i = 0; i < 600; i++) {
      conv.step(DT)
      expect(conv.level).toBeGreaterThanOrEqual(0)
      expect(conv.level).toBeLessThanOrEqual(1)
    }
  })
})

describe('Conversation with a live mic', () => {
  it('finishes the turn on its own after the user pauses', async () => {
    const mic = new FakeMic()
    const conv = new Conversation({ rng: seededRng(4), mic })
    conv.toggleMic()
    await flush()
    expect(conv.liveMic).toBe(true)
    mic.level = 0.8
    run(conv, 1.5)
    mic.level = 0
    run(conv, 1.4)
    expect(conv.mode).toBe('listening')
    run(conv, 0.3)
    expect(conv.mode).toBe('thinking')
    expect(mic.stopped).toBe(1)
    run(conv, 2)
    expect(fill(SHORT_REPLIES, 'friend')).toContain(conv.speech?.text) // ~1.5 s of talking
  })

  it('falls back to a simulation when the mic is blocked', async () => {
    const notices: string[] = []
    const mic = new FakeMic()
    mic.start = () => Promise.reject(new Error('denied'))
    const conv = new Conversation({ rng: seededRng(5), mic })
    conv.onNotice((n) => notices.push(n))
    conv.toggleMic()
    await flush()
    expect(notices).toEqual(['Microphone blocked, simulating your voice'])
    run(conv, 3)
    expect(conv.level).toBeGreaterThan(0)
  })
})

describe('Conversation with a voice', () => {
  it('waits for the voice to finish, then goes idle', () => {
    const speaker = new FakeSpeaker()
    const conv = new Conversation({ rng: seededRng(6), speaker })
    conv.toggleMic()
    conv.toggleMic()
    run(conv, 2)
    expect(conv.mode).toBe('speaking')
    expect(speaker.spoken).toHaveLength(1)
    run(conv, conv.speech!.duration + 1) // captions done, but the voice is still talking
    expect(conv.mode).toBe('speaking')
    speaker.callbacks?.onEnd()
    run(conv, DT)
    expect(conv.mode).toBe('idle')
    expect(conv.speech?.wordProgress().every((p) => p === 1)).toBe(true)
  })

  it('stops the voice when interrupted', () => {
    const speaker = new FakeSpeaker()
    const conv = new Conversation({ rng: seededRng(7), speaker })
    conv.toggleMic()
    conv.toggleMic()
    run(conv, 2)
    conv.cancel()
    expect(speaker.stopped).toBe(1)
  })

  it('shows captions only when the voice fails', () => {
    const notices: string[] = []
    const speaker = new FakeSpeaker()
    const conv = new Conversation({ rng: seededRng(8), speaker })
    conv.onNotice((n) => notices.push(n))
    conv.toggleMic()
    conv.toggleMic()
    run(conv, 2)
    speaker.callbacks?.onError()
    run(conv, 20)
    expect(conv.mode).toBe('idle')
    expect(notices).toEqual(['Voice unavailable in this browser, showing captions only'])
  })
})

describe('chooseReply', () => {
  const rng = seededRng(9)
  it('matches how much was said', () => {
    const pick = (talkTime: number, transcript = '') =>
      chooseReply(rng, { name: 'Ada', talkTime, transcript }).text
    expect(fill(NO_SPEECH_REPLIES, 'Ada')).toContain(pick(0))
    expect(fill(SHORT_REPLIES, 'Ada')).toContain(pick(1))
    expect(fill(LONG_REPLIES, 'Ada')).toContain(pick(5))
    expect(fill(SHORT_REPLIES, 'Ada')).toContain(pick(0, 'hello there'))
  })

  it('can quote what it heard', () => {
    const texts = Array.from({ length: 20 }, () =>
      chooseReply(rng, {
        name: 'Ada',
        talkTime: 3,
        transcript: 'I want to plan a trip to Lagos next month.',
      }),
    )
    const quoted = texts.find((r) => HEARD_REPLIES.includes(r.template))
    expect(quoted?.text).toContain('"I want to plan a trip..."')
  })
})

it('counts syllables', () => {
  expect(countSyllables('hi')).toBe(1)
  expect(countSyllables('favourite,')).toBe(3)
})
