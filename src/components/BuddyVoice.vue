<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import AppIcon from './AppIcon.vue'
import { BrowserMic, BrowserRecognizer, BrowserSpeaker } from '@/buddy/audio'
import { Buddy } from '@/buddy/renderer'
import {
  approach,
  Conversation,
  type Mode,
  type SpeechTimeline,
  type VoiceStyle,
} from '@/buddy/voice'

const props = defineProps<{ name: string }>()

// Each model speaks with a different voice (by rank among English voices) and pace.
const MODELS = {
  Waza: { voiceIndex: 0, rate: 1, pitch: 1 },
  'Waza Pro': { voiceIndex: 1, rate: 0.95, pitch: 0.85 },
  'Waza Mini': { voiceIndex: 2, rate: 1.1, pitch: 1.2 },
} satisfies Record<string, VoiceStyle>
type ModelName = keyof typeof MODELS
const modelNames = Object.keys(MODELS) as ModelName[]

const speaker = BrowserSpeaker.supported() ? new BrowserSpeaker() : null
const conversation = new Conversation({
  name: props.name,
  mic: BrowserMic.supported() ? new BrowserMic() : null,
  speaker,
  recognizer: BrowserRecognizer.supported() ? new BrowserRecognizer() : null,
})
const buddy = new Buddy()

const mode = ref<Mode>('idle')
const transcript = ref('')
const liveMic = ref(false)
const captionWords = shallowRef<string[]>([])
const captionProgress = shallowRef<number[]>([])
const model = ref<ModelName>('Waza')
const menuOpen = ref(false)
const toastText = ref('')
const toastVisible = ref(false)
const textTop = ref(0)

const screen = ref<HTMLElement>()
const canvas = ref<HTMLCanvasElement>()
const micButton = ref<HTMLButtonElement>()
const modelMenu = ref<HTMLElement>()

conversation.onNotice(showToast)

// ------------------------------------------------------------------ layout

let width = 0
let height = 0

/** Fit buddy + caption block between the top buttons and the mic. */
function geometry() {
  const top = 84
  const bottom = height - 208
  const free = bottom - top - 120
  return {
    cx: width / 2,
    cy: top + free / 2 + 10,
    R: Math.max(40, Math.min(Math.min(width, 520) * 0.21, free * 0.26)),
  }
}

function resize() {
  const el = screen.value
  const cv = canvas.value
  if (!el || !cv) return
  width = el.clientWidth
  height = el.clientHeight
  const dpr = Math.min(window.devicePixelRatio || 1, 2.5)
  cv.width = Math.round(width * dpr)
  cv.height = Math.round(height * dpr)
  const { cy, R } = geometry()
  textTop.value = cy + R * 1.85
}

// ------------------------------------------------------------------- frame

let raf = 0
let last = 0
let micGlow = 0
let captionSource: SpeechTimeline | null = null

function frame(now: number) {
  const dt = last ? Math.min((now - last) / 1000, 0.05) : 0.016
  last = now
  conversation.step(dt)
  buddy.step(dt, conversation.mode, conversation.level)
  draw()
  syncUi(dt)
  raf = requestAnimationFrame(frame)
}

function draw() {
  const cv = canvas.value
  const ctx = cv?.getContext('2d')
  if (!cv || !ctx || !width) return
  ctx.setTransform(cv.width / width, 0, 0, cv.height / height, 0, 0)
  ctx.fillStyle = '#161616'
  ctx.fillRect(0, 0, width, height)

  // Blue glow rising from the bottom, stronger while talking.
  const w = buddy.weights
  const active = 1 - w.idle
  const alpha = 95 + 60 * active + 60 * buddy.level * (w.listening + w.speaking)
  const radius = Math.min(width, 720) * (0.95 + 0.1 * active)
  ctx.save()
  ctx.translate(width / 2, height + 30)
  ctx.scale(1, 0.62)
  const g = ctx.createRadialGradient(0, 0, 0, 0, 0, radius)
  g.addColorStop(0, `rgba(78,112,158,${alpha / 255})`)
  g.addColorStop(0.45, `rgba(52,76,110,${(alpha * 0.55) / 255})`)
  g.addColorStop(1, 'rgba(30,40,56,0)')
  ctx.fillStyle = g
  ctx.beginPath()
  ctx.arc(0, 0, radius, 0, Math.PI * 2)
  ctx.fill()
  ctx.restore()

  const { cx, cy, R } = geometry()
  buddy.paint(ctx, cx, cy, R)
}

function syncUi(dt: number) {
  if (mode.value !== conversation.mode) mode.value = conversation.mode
  if (transcript.value !== conversation.transcript) transcript.value = conversation.transcript
  if (liveMic.value !== conversation.liveMic) liveMic.value = conversation.liveMic
  const speech = conversation.speech
  if (speech && speech !== captionSource) {
    captionSource = speech
    captionWords.value = speech.words.map((w) => w.text)
  }
  if (speech && conversation.mode === 'speaking') captionProgress.value = speech.wordProgress()

  const listening = conversation.mode === 'listening'
  micGlow = approach(micGlow, listening ? 0.35 + 0.65 * conversation.level : 0, 12, dt)
  micButton.value?.style.setProperty('--glow', micGlow.toFixed(3))
}

// ------------------------------------------------------------------- input

function onMic() {
  speaker?.unlock()
  conversation.toggleMic()
}

function onClose() {
  if (conversation.mode === 'idle') showToast("Tap the mic whenever you're ready")
  else conversation.cancel()
}

function chooseModel(name: ModelName) {
  menuOpen.value = false
  if (name === model.value) return
  model.value = name
  conversation.voice = MODELS[name]
  showToast(`Switched to ${name}`)
}

function onKey(e: KeyboardEvent) {
  const onButton = e.target instanceof HTMLElement && e.target.closest('button')
  if (e.code === 'Space' && !e.repeat && !onButton) {
    e.preventDefault()
    onMic()
  } else if (e.key === 'Escape') {
    menuOpen.value = false
    conversation.cancel()
  }
}

function onPointerDown(e: PointerEvent) {
  if (menuOpen.value && !modelMenu.value?.contains(e.target as Node)) menuOpen.value = false
}

let toastTimer = 0
function showToast(text: string) {
  toastText.value = text
  toastVisible.value = true
  clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => (toastVisible.value = false), 1900)
}

// Caption word colour: dim grey -> warm white as it is spoken.
function wordStyle(i: number) {
  const k = captionProgress.value[i] ?? 0
  const e = Math.sqrt(k)
  const mix = (a: number, b: number) => Math.round(a + (b - a) * e)
  return {
    color: `rgb(${mix(92, 234)},${mix(92, 229)},${mix(96, 220)})`,
    top: k > 0 && k < 1 ? `${(1 - k) * 3}px` : '0',
  }
}

let observer: ResizeObserver | null = null

onMounted(() => {
  resize()
  observer = new ResizeObserver(resize)
  if (screen.value) observer.observe(screen.value)
  window.addEventListener('keydown', onKey)
  window.addEventListener('pointerdown', onPointerDown)
  raf = requestAnimationFrame(frame)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  observer?.disconnect()
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('pointerdown', onPointerDown)
  conversation.cancel()
})
</script>

<template>
  <main ref="screen" class="screen" :class="`mode-${mode}`">
    <canvas ref="canvas" class="stage" aria-hidden="true" />

    <header class="top-bar">
      <button
        class="round"
        aria-label="Conversation history"
        @click="showToast('Conversation history is coming soon')"
      >
        <AppIcon name="menu" />
      </button>
      <button class="round" aria-label="Settings" @click="showToast('Settings are coming soon')">
        <AppIcon name="gear" />
      </button>
    </header>

    <section class="talk" :style="{ top: `${textTop}px` }" aria-live="polite">
      <div class="layer" :class="{ on: mode === 'idle' }">
        <h1 class="greeting">Let's talk, {{ name }}</h1>
        <p class="hint">Tap the mic or press Space</p>
      </div>

      <div class="layer" :class="{ on: mode === 'listening' }">
        <p class="status listening">
          Listening<span class="dots"><i>.</i><i>.</i><i>.</i></span>
        </p>
        <p v-if="transcript" class="transcript">“{{ transcript }}”</p>
        <p v-else class="hint">
          {{
            liveMic
              ? "I'll reply when you pause · Tap the mic to finish"
              : "Tap the mic when you're done · Esc to cancel"
          }}
        </p>
      </div>

      <div class="layer" :class="{ on: mode === 'thinking' }">
        <p class="status thinking">
          Thinking<span class="dots"><i>.</i><i>.</i><i>.</i></span>
        </p>
      </div>

      <div class="layer captions" :class="{ on: mode === 'speaking' }">
        <p>
          <template v-for="(word, i) in captionWords" :key="i">
            <span :style="wordStyle(i)">{{ word }}</span
            >{{ ' ' }}
          </template>
        </p>
      </div>
    </section>

    <button
      ref="micButton"
      class="mic"
      :class="{ active: mode === 'listening' }"
      :aria-label="mode === 'listening' ? 'Finish speaking' : 'Start talking'"
      :aria-pressed="mode === 'listening'"
      @click="onMic"
    >
      <AppIcon name="mic" :size="30" />
    </button>

    <footer class="bottom-bar">
      <button
        class="round big"
        aria-label="Add attachment"
        @click="showToast('Attachments are coming soon')"
      >
        <AppIcon name="plus" :size="26" />
      </button>

      <div ref="modelMenu" class="model">
        <button
          class="pill"
          :aria-expanded="menuOpen"
          aria-haspopup="listbox"
          @click="menuOpen = !menuOpen"
        >
          {{ model }} <AppIcon name="updown" :size="17" />
        </button>
        <Transition name="pop">
          <ul v-if="menuOpen" class="menu" role="listbox">
            <li v-for="m in modelNames" :key="m">
              <button role="option" :aria-selected="m === model" @click="chooseModel(m)">
                <span class="check">{{ m === model ? '✓' : '' }}</span
                >{{ m }}
              </button>
            </li>
          </ul>
        </Transition>
      </div>

      <button class="round big light" aria-label="End conversation" @click="onClose">
        <AppIcon name="close" :size="26" />
      </button>
    </footer>

    <div class="toast" :class="{ show: toastVisible }" role="status">{{ toastText }}</div>
  </main>
</template>

<style scoped>
.screen {
  position: relative;
  height: 100dvh;
  overflow: hidden;
  background: #161616;
  color: #eae5dc;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
}

.stage {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

button {
  cursor: pointer;
  border: none;
  color: inherit;
  font: inherit;
}

button:focus-visible {
  outline: 2px solid #8fb6ff;
  outline-offset: 3px;
}

.round {
  width: 54px;
  height: 54px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: rgba(34, 34, 34, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.11);
  color: #ececec;
  transition:
    background 0.16s,
    border-color 0.16s,
    transform 0.11s;
}

.round:hover {
  background: rgba(50, 50, 50, 0.95);
  border-color: rgba(255, 255, 255, 0.22);
}

.round:active,
.pill:active {
  transform: scale(0.93);
}

.round.big {
  width: 60px;
  height: 60px;
}

.round.light {
  background: #eeeae4;
  color: #1e1e1e;
  border-color: rgba(255, 255, 255, 0.35);
}

.round.light:hover {
  background: #fff;
}

.top-bar {
  position: absolute;
  top: calc(24px + env(safe-area-inset-top));
  /* Phone-width controls, centred on wide screens. */
  left: max(22px, calc(50% - 238px));
  right: max(22px, calc(50% - 238px));
  display: flex;
  justify-content: space-between;
}

/* ---- text under the buddy ---- */

.talk {
  position: absolute;
  left: 0;
  right: 0;
  pointer-events: none;
}

.layer {
  position: absolute;
  inset: 0 0 auto;
  padding: 0 32px;
  text-align: center;
  opacity: 0;
  transform: translateY(6px);
  transition:
    opacity 0.35s ease,
    transform 0.35s ease;
}

.layer.on {
  opacity: 1;
  transform: none;
}

.greeting {
  font-family: 'Newsreader', Georgia, 'Times New Roman', serif;
  font-weight: 400;
  font-size: 32px;
  letter-spacing: -0.01em;
  line-height: 1.25;
  color: #eae5dc;
}

.hint {
  margin-top: 12px;
  font-size: 13px;
  color: #929296;
}

.status {
  font-size: 20px;
  line-height: 1.4;
}

.status.listening {
  color: #c4d6f5;
}

.status.thinking {
  color: #f0d6c8;
}

.dots {
  position: absolute;
}

.dots i {
  font-style: normal;
  animation: dot 1.4s infinite;
}

.dots i:nth-child(2) {
  animation-delay: 0.2s;
}

.dots i:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes dot {
  0%,
  100% {
    opacity: 0.15;
  }
  40% {
    opacity: 1;
  }
}

.transcript {
  margin: 10px auto 0;
  max-width: 420px;
  font-size: 15px;
  font-style: italic;
  line-height: 1.45;
  color: #d6d2ca;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.captions p {
  max-width: 520px;
  margin: 0 auto;
  font-size: 18.5px;
  line-height: 1.55;
}

.captions span {
  position: relative;
  transition: color 0.12s linear;
}

/* ---- mic ---- */

.mic {
  --glow: 0;
  position: absolute;
  left: 50%;
  bottom: calc(116px + env(safe-area-inset-bottom));
  width: 92px;
  height: 92px;
  margin-left: -46px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: #f0f4fa;
  background: radial-gradient(circle at 50% 22%, rgb(40, 66, 102), rgb(18, 32, 54) 75%);
  border: 1.4px solid rgba(110, 160, 230, 0.45);
  box-shadow:
    0 0 calc(22px + 46px * var(--glow)) calc(4px + 14px * var(--glow))
      rgba(80, 140, 230, calc(0.22 + 0.45 * var(--glow))),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  transition:
    background 0.3s,
    border-color 0.3s,
    transform 0.11s;
}

.mic:hover {
  border-color: rgba(140, 185, 245, 0.7);
}

.mic:active {
  transform: scale(0.94);
}

.mic.active {
  background: radial-gradient(circle at 50% 22%, rgb(70, 112, 162), rgb(32, 58, 94) 75%);
  border-color: rgba(140, 185, 250, 0.9);
}

.mic::before,
.mic::after {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 50%;
  border: 1.5px solid rgba(150, 190, 255, 0.6);
  opacity: 0;
  pointer-events: none;
}

.mic.active::before,
.mic.active::after {
  animation: pulse 1.1s ease-out infinite;
}

.mic.active::after {
  animation-delay: 0.55s;
}

@keyframes pulse {
  from {
    transform: scale(1);
    opacity: 0.8;
  }
  to {
    transform: scale(1.75);
    opacity: 0;
  }
}

/* ---- bottom bar ---- */

.bottom-bar {
  position: absolute;
  left: max(26px, calc(50% - 234px));
  right: max(26px, calc(50% - 234px));
  bottom: calc(14px + env(safe-area-inset-bottom));
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.model {
  position: relative;
}

.pill {
  height: 54px;
  min-width: 136px;
  padding: 0 22px;
  border-radius: 27px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: 16px;
  color: #eceef2;
  background: rgba(36, 44, 56, 0.88);
  border: 1px solid rgba(255, 255, 255, 0.12);
  transition:
    background 0.16s,
    transform 0.11s;
}

.pill:hover {
  background: rgba(50, 58, 70, 0.92);
}

.menu {
  position: absolute;
  bottom: 64px;
  left: 50%;
  translate: -50% 0;
  min-width: 170px;
  margin: 0;
  padding: 6px;
  list-style: none;
  background: #232830;
  border: 1px solid #3a414c;
  border-radius: 14px;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.45);
}

.menu button {
  width: 100%;
  padding: 10px 14px;
  border-radius: 9px;
  background: transparent;
  text-align: left;
  font-size: 15px;
  color: #eceef2;
}

.menu button:hover {
  background: #34404f;
}

.check {
  display: inline-block;
  width: 22px;
  color: #9cc0ff;
}

.pop-enter-active,
.pop-leave-active {
  transition:
    opacity 0.16s,
    transform 0.16s;
}

.pop-enter-from,
.pop-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

/* ---- toast ---- */

.toast {
  position: absolute;
  top: calc(100px + env(safe-area-inset-top));
  left: 50%;
  translate: -50% 0;
  max-width: calc(100% - 40px);
  padding: 8px 16px;
  border-radius: 16px;
  background: rgba(44, 44, 46, 0.94);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #eee;
  font-size: 14px;
  white-space: nowrap;
  opacity: 0;
  transform: translateY(-6px);
  transition:
    opacity 0.22s,
    transform 0.22s;
  pointer-events: none;
}

.toast.show {
  opacity: 1;
  transform: none;
}

@media (prefers-reduced-motion: reduce) {
  .mic.active::before,
  .mic.active::after,
  .dots i {
    animation: none;
  }
}
</style>
