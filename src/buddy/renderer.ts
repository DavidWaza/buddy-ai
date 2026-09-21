/**
 * The buddy: a squishy coral blob with a face, halos, rings and bubbles,
 * drawn on a 2D canvas. Particle positions are stored in units of the buddy
 * radius relative to its centre, so the scene scales with the viewport.
 */

import { approach, MODES, type Mode } from './voice'

const TAU = Math.PI * 2
const BLINK_SECONDS = 0.16

type RGB = readonly [number, number, number]
const INK: RGB = [66, 26, 18]
const CORAL_LIGHT: RGB = [255, 196, 170]
const CORAL: RGB = [232, 128, 94]
const CORAL_DEEP: RGB = [176, 76, 50]
const LISTEN_BLUE: RGB = [150, 188, 255]
const SPEAK_WARM: RGB = [255, 196, 176]
const RING: RGB = [255, 160, 130]

/** `alpha` is 0-255, matching the original Qt version. */
export function rgba(c: RGB, alpha: number): string {
  return `rgba(${c[0]},${c[1]},${c[2]},${Math.max(0, Math.min(255, alpha)) / 255})`
}

const brighten = (c: RGB, by: number): RGB =>
  [Math.min(255, c[0] + by), Math.min(255, c[1] + by), Math.min(255, c[2] + by)] as const

function gauss(): number {
  return Math.sqrt(-2 * Math.log(1 - Math.random())) * Math.cos(TAU * Math.random())
}

const rand = (lo: number, hi: number) => lo + (hi - lo) * Math.random()

/** A smooth closed outline whose radius is perturbed by layered sine waves. */
export function blobPath(
  cx: number,
  cy: number,
  rx: number,
  ry: number,
  t: number,
  wobble: number,
  spin: number,
  points = 72,
): Path2D {
  const pts: [number, number][] = []
  for (let i = 0; i < points; i++) {
    const a = (TAU * i) / points
    const d =
      0.55 * Math.sin(2 * a + t * 0.9 + spin) +
      0.45 * Math.sin(3 * a - t * 1.4 + 1.7) +
      0.3 * Math.sin(5 * a + t * 2.1 - spin * 0.5) +
      0.18 * Math.sin(7 * a - t * 3.0)
    const k = 1 + wobble * d
    pts.push([cx + rx * k * Math.cos(a), cy + ry * k * Math.sin(a)])
  }
  const path = new Path2D()
  const first = pts[0]!
  const last = pts[points - 1]!
  path.moveTo((last[0] + first[0]) / 2, (last[1] + first[1]) / 2)
  for (let i = 0; i < points; i++) {
    const p = pts[i]!
    const q = pts[(i + 1) % points]!
    path.quadraticCurveTo(p[0], p[1], (p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
  }
  path.closePath()
  return path
}

interface Bubble {
  x: number
  y: number
  vx: number
  vy: number
  r: number
  inward: boolean
  life: number
  seed: number
  age: number
  dead: boolean
}

function bubbleAlpha(b: Bubble): number {
  const fadeIn = Math.min(1, b.age / 0.2)
  const fadeOut = b.inward
    ? Math.max(0, Math.min(1, (Math.hypot(b.x, b.y) - 1.02) / 0.35))
    : Math.max(0, Math.min(1, (b.life - b.age) / (b.life * 0.4)))
  return fadeIn * fadeOut
}

interface Ring {
  age: number
  life: number
}

export class Buddy {
  t = 0
  level = 0
  weights: Record<Mode, number> = { idle: 1, listening: 0, thinking: 0, speaking: 0 }
  private bubbles: Bubble[] = []
  private rings: Ring[] = []
  private spin = 0
  private blinkIn = 2
  private blinkT = -1
  private gaze: [number, number] = [0, 0]
  private gazeTarget: [number, number] = [0, 0]
  private gazeRetargetIn = 0
  private emitIn = 0
  private emitOut = 0
  private ringCooldown = 0
  private lastLevel = 0

  // ------------------------------------------------------------------ update

  step(dt: number, mode: Mode, level: number): void {
    this.t += dt
    this.level = level
    for (const m of MODES) this.weights[m] = approach(this.weights[m], m === mode ? 1 : 0, 7, dt)
    const w = this.weights
    const t = this.t
    this.spin += dt * (0.4 + 2.2 * w.thinking)

    // Blinking, with the occasional double blink.
    if (this.blinkT >= 0) {
      this.blinkT += dt
      if (this.blinkT > BLINK_SECONDS) this.blinkT = -1
    } else {
      this.blinkIn -= dt
      if (this.blinkIn <= 0) {
        this.blinkT = 0
        this.blinkIn = Math.random() < 0.2 ? 0.22 : rand(2.2, 5.5)
      }
    }

    // Where the eyes look.
    if (mode === 'thinking') {
      this.gazeTarget = [0.6 * Math.cos(t * 1.6), -0.6 + 0.25 * Math.sin(t * 1.6)]
    } else if (mode === 'listening') {
      this.gazeTarget = [0.15 * Math.sin(t * 0.7), -0.25]
    } else if (mode === 'speaking') {
      this.gazeTarget = [0.25 * Math.sin(t * 0.9), 0.05 * Math.sin(t * 1.7)]
    } else {
      this.gazeRetargetIn -= dt
      if (this.gazeRetargetIn <= 0) {
        this.gazeRetargetIn = rand(1.5, 4)
        this.gazeTarget = [rand(-0.6, 0.6), rand(-0.3, 0.3)]
      }
    }
    this.gaze[0] = approach(this.gaze[0], this.gazeTarget[0], 6, dt)
    this.gaze[1] = approach(this.gaze[1], this.gazeTarget[1], 6, dt)

    // Listening pulls bubbles in; speaking blows them out.
    this.emitIn += dt * w.listening * (1.5 + 14 * level)
    for (; this.emitIn >= 1; this.emitIn--) this.spawnInward()
    this.emitOut += dt * w.speaking * (1 + 16 * level)
    for (; this.emitOut >= 1; this.emitOut--) this.spawnOutward()

    // A ripple ring on every syllable peak while speaking.
    this.ringCooldown -= dt
    if (mode === 'speaking' && level > 0.45 && this.lastLevel <= 0.45 && this.ringCooldown <= 0) {
      this.rings.push({ age: 0, life: 1.4 })
      this.ringCooldown = 0.25
    }
    this.lastLevel = level

    for (const b of this.bubbles) {
      b.age += dt
      if (b.inward) {
        b.x += b.vx * dt
        b.y += b.vy * dt
        if (Math.hypot(b.x, b.y) < 1.04) b.dead = true
      } else {
        b.vy -= 0.25 * dt
        b.vx += Math.sin(t * 4 + b.seed) * 0.3 * dt
        b.x += b.vx * dt
        b.y += b.vy * dt
        if (b.age >= b.life) b.dead = true
      }
    }
    this.bubbles = this.bubbles.filter((b) => !b.dead)

    for (const r of this.rings) r.age += dt
    this.rings = this.rings.filter((r) => r.age < r.life)
  }

  private spawnInward(): void {
    const a = rand(0, TAU)
    const dist = rand(1.9, 2.6)
    const speed = rand(0.5, 0.95)
    const swirl = rand(-0.25, 0.25)
    this.bubbles.push({
      x: Math.cos(a) * dist,
      y: Math.sin(a) * dist,
      vx: -Math.cos(a) * speed - Math.sin(a) * swirl,
      vy: -Math.sin(a) * speed + Math.cos(a) * swirl,
      r: rand(0.03, 0.08),
      inward: true,
      life: 10,
      seed: rand(0, TAU),
      age: 0,
      dead: false,
    })
  }

  private spawnOutward(): void {
    const a = -Math.PI / 2 + gauss() * 0.9
    const speed = rand(0.35, 0.8)
    this.bubbles.push({
      x: Math.cos(a),
      y: Math.sin(a),
      vx: Math.cos(a) * speed,
      vy: Math.sin(a) * speed - 0.25,
      r: rand(0.03, 0.11),
      inward: false,
      life: rand(1.8, 3),
      seed: rand(0, TAU),
      age: 0,
      dead: false,
    })
  }

  // ------------------------------------------------------------------- paint

  paint(ctx: CanvasRenderingContext2D, cx: number, cy: number, R: number): void {
    const w = this.weights
    const { listening: listen, speaking: speak, thinking: think, idle } = w
    const { level, t } = this
    const voice = listen + speak

    const bob = Math.sin(t * 1.3) * R * 0.045 * (idle + think) - level * speak * R * 0.05
    const by = cy + bob
    const scale = 1 + 0.025 * Math.sin(t * 1.6) + 0.1 * level * voice
    const rx = R * scale * (1 + 0.035 * level * speak)
    const ry = R * scale * (0.97 - 0.035 * level * speak)
    const wobble =
      0.018 + listen * (0.02 + 0.07 * level) + speak * (0.015 + 0.08 * level) + think * 0.02

    this.paintGlow(ctx, cx, by, R, listen, voice, think)
    this.paintHalos(ctx, cx, by, R, listen, wobble)
    this.paintRings(ctx, cx, by, R)
    this.paintShadow(ctx, cx, cy, R, bob)

    const body = blobPath(cx, by, rx, ry, t, wobble, this.spin)
    this.paintBody(ctx, body, cx, by, R)
    this.paintFace(ctx, cx, by, R * scale, listen, speak, think, idle)
    this.paintThinkingDots(ctx, cx, by, R, think)
    this.paintBubbles(ctx, cx, by, R)
  }

  private fillCircle(ctx: CanvasRenderingContext2D, x: number, y: number, r: number): void {
    ctx.beginPath()
    ctx.arc(x, y, Math.max(0, r), 0, TAU)
    ctx.fill()
  }

  private paintGlow(
    ctx: CanvasRenderingContext2D,
    cx: number,
    cy: number,
    R: number,
    listen: number,
    voice: number,
    think: number,
  ): void {
    const level = this.level
    let radius = R * (2.1 + 0.8 * level * voice)
    const alpha = 38 + 110 * level * voice + 25 * think
    let g = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius)
    g.addColorStop(0, rgba(CORAL, alpha))
    g.addColorStop(0.5, rgba(CORAL, alpha * 0.3))
    g.addColorStop(1, rgba(CORAL, 0))
    ctx.fillStyle = g
    this.fillCircle(ctx, cx, cy, radius)
    if (listen > 0.01) {
      radius = R * (2.4 + 0.6 * level)
      g = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius)
      g.addColorStop(0.35, rgba(LISTEN_BLUE, 60 * listen * (0.4 + level)))
      g.addColorStop(1, rgba(LISTEN_BLUE, 0))
      ctx.fillStyle = g
      this.fillCircle(ctx, cx, cy, radius)
    }
  }

  private paintHalos(
    ctx: CanvasRenderingContext2D,
    cx: number,
    cy: number,
    R: number,
    listen: number,
    wobble: number,
  ): void {
    if (listen < 0.01) return
    ctx.lineWidth = 1.6
    ;[1.22, 1.42, 1.64].forEach((base, i) => {
      const s = base + 0.2 * this.level * (1 - i * 0.2) + 0.02 * Math.sin(this.t * 2 + i)
      ctx.strokeStyle = rgba(LISTEN_BLUE, listen * (75 - i * 20) * (0.5 + this.level))
      ctx.stroke(blobPath(cx, cy, R * s, R * s, this.t + i * 0.7, wobble * 1.3, -this.spin))
    })
  }

  private paintRings(ctx: CanvasRenderingContext2D, cx: number, cy: number, R: number): void {
    for (const ring of this.rings) {
      const k = ring.age / ring.life
      ctx.strokeStyle = rgba(RING, 120 * (1 - k) ** 2)
      ctx.lineWidth = 0.6 + 2.2 * (1 - k)
      ctx.beginPath()
      ctx.arc(cx, cy, R * (1.05 + 1.3 * k), 0, TAU)
      ctx.stroke()
    }
  }

  private paintShadow(
    ctx: CanvasRenderingContext2D,
    cx: number,
    cy: number,
    R: number,
    bob: number,
  ): void {
    const lift = Math.max(0.6, 1 - bob / R)
    const sx = R * lift
    const sy = R * 0.13 * lift
    const y = cy + R * 1.38
    ctx.save()
    ctx.translate(cx, y)
    ctx.scale(1, sy / sx)
    const g = ctx.createRadialGradient(0, 0, 0, 0, 0, sx)
    g.addColorStop(0, 'rgba(0,0,0,0.47)')
    g.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = g
    this.fillCircle(ctx, 0, 0, sx)
    ctx.restore()
  }

  private paintBody(
    ctx: CanvasRenderingContext2D,
    body: Path2D,
    cx: number,
    cy: number,
    R: number,
  ): void {
    const lift = Math.round(18 * this.level)
    const gx = cx - R * 0.32
    const gy = cy - R * 0.38
    const g = ctx.createRadialGradient(gx, gy, 0, gx, gy, R * 1.55)
    g.addColorStop(0, rgba(brighten(CORAL_LIGHT, lift), 255))
    g.addColorStop(0.45, rgba(brighten(CORAL, lift), 255))
    g.addColorStop(1, rgba(CORAL_DEEP, 255))
    ctx.fillStyle = g
    ctx.fill(body)

    // Soft specular highlight, clipped to the body.
    ctx.save()
    ctx.clip(body)
    const hx = cx - R * 0.38
    const hy = cy - R * 0.5
    const hg = ctx.createRadialGradient(hx, hy, 0, hx, hy, R * 0.45)
    hg.addColorStop(0, 'rgba(255,255,255,0.43)')
    hg.addColorStop(1, 'rgba(255,255,255,0)')
    ctx.fillStyle = hg
    this.fillCircle(ctx, hx, hy, R * 0.45)
    ctx.restore()

    ctx.strokeStyle = 'rgba(255,214,196,0.22)'
    ctx.lineWidth = 1.5
    ctx.stroke(body)
  }

  private paintFace(
    ctx: CanvasRenderingContext2D,
    cx: number,
    cy: number,
    R: number,
    listen: number,
    speak: number,
    think: number,
    idle: number,
  ): void {
    const [gx, gy] = this.gaze
    const level = this.level
    const fx = cx + gx * R * 0.05
    const fy = cy + gy * R * 0.04

    // Eyes.
    const openness =
      this.blinkT >= 0 ? 1 - Math.sin((Math.PI * this.blinkT) / BLINK_SECONDS) * 0.92 : 1
    const eyeW = R * 0.135 * (1 + 0.08 * listen)
    const eyeH = R * 0.215 * (1 + 0.12 * listen) * openness * (1 - 0.15 * speak * level)
    for (const side of [-1, 1]) {
      const ex = fx + side * R * 0.33 + gx * R * 0.07
      const ey = fy - R * 0.1 + gy * R * 0.06
      ctx.fillStyle = rgba(INK, 255)
      ctx.beginPath()
      ctx.ellipse(ex, ey, eyeW / 2, eyeH / 2, 0, 0, TAU)
      ctx.fill()
      if (openness > 0.5) {
        ctx.fillStyle = 'rgba(255,255,255,0.9)'
        this.fillCircle(ctx, ex - eyeW * 0.16, ey - eyeH * 0.2, eyeW * 0.19)
      }
    }

    // Cheeks.
    ctx.fillStyle = `rgba(255,118,110,${(50 + 60 * speak * level + 20 * listen) / 255})`
    for (const side of [-1, 1]) {
      ctx.beginPath()
      ctx.ellipse(fx + side * R * 0.56, fy + R * 0.13, R * 0.12, R * 0.07, 0, 0, TAU)
      ctx.fill()
    }

    // Mouth: a smile that opens into a talking mouth with the voice level.
    const mx = fx + gx * R * 0.04 + think * R * 0.07
    const my = fy + R * 0.2
    const talk = speak * level
    const smileAlpha = 255 * Math.max(0, 1 - talk * 7)
    if (smileAlpha > 1) {
      const curve = idle + listen * 0.65 + think * 0.1 + speak * 0.9
      const half = R * 0.13 * (1 - 0.35 * think)
      ctx.strokeStyle = rgba(INK, smileAlpha)
      ctx.lineWidth = R * 0.045
      ctx.lineCap = 'round'
      ctx.beginPath()
      ctx.moveTo(mx - half, my)
      ctx.quadraticCurveTo(mx, my + R * 0.12 * curve, mx + half, my - R * 0.02 * think)
      ctx.stroke()
    }
    if (talk > 0.03) {
      const mw = R * (0.11 - 0.02 * talk)
      const mh = R * (0.025 + 0.13 * talk)
      const mouth = new Path2D()
      mouth.ellipse(mx, my + mh * 0.3, mw, mh, 0, 0, TAU)
      const a = Math.min(1, talk * 7)
      ctx.fillStyle = rgba(INK, 255 * a)
      ctx.fill(mouth)
      ctx.save()
      ctx.clip(mouth)
      ctx.fillStyle = `rgba(236,112,96,${a})`
      ctx.beginPath()
      ctx.ellipse(mx, my + mh * 1.1, mw * 0.8, mh * 0.7, 0, 0, TAU)
      ctx.fill()
      ctx.restore()
    }
  }

  private paintThinkingDots(
    ctx: CanvasRenderingContext2D,
    cx: number,
    cy: number,
    R: number,
    think: number,
  ): void {
    if (think < 0.01) return
    ;[0.075, 0.058, 0.042].forEach((size, i) => {
      const a = this.spin * 1.6 - i * 0.45
      ctx.fillStyle = `rgba(255,206,186,${(think * (230 - i * 60)) / 255})`
      this.fillCircle(ctx, cx + Math.cos(a) * R * 1.5, cy + Math.sin(a) * R * 1.5, R * size)
    })
  }

  private paintBubbles(ctx: CanvasRenderingContext2D, cx: number, cy: number, R: number): void {
    for (const b of this.bubbles) {
      const a = bubbleAlpha(b)
      if (a <= 0.01) continue
      const x = cx + b.x * R
      const y = cy + b.y * R
      const r = b.r * R
      const tint = b.inward ? LISTEN_BLUE : SPEAK_WARM
      const g = ctx.createRadialGradient(
        x - r * 0.3,
        y - r * 0.3,
        0,
        x - r * 0.3,
        y - r * 0.3,
        r * 1.3,
      )
      g.addColorStop(0, `rgba(255,255,255,${(70 * a) / 255})`)
      g.addColorStop(0.7, rgba(tint, 25 * a))
      g.addColorStop(1, rgba(tint, 70 * a))
      ctx.fillStyle = g
      ctx.strokeStyle = rgba(tint, 180 * a)
      ctx.lineWidth = Math.max(1, r * 0.12)
      ctx.beginPath()
      ctx.arc(x, y, r, 0, TAU)
      ctx.fill()
      ctx.stroke()
      ctx.fillStyle = `rgba(255,255,255,${(210 * a) / 255})`
      this.fillCircle(ctx, x - r * 0.35, y - r * 0.4, r * 0.22)
    }
  }
}
