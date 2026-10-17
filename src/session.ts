/**
 * Dummy sign-in. There is no account and no password check: whoever signs in
 * simply gives the buddy the name it greets them by. The name is kept in this
 * browser only (localStorage), which can be unavailable in private windows, so
 * every access is guarded.
 */

import { ref } from 'vue'

const KEY = 'buddy-ai:user'
export const MAX_NAME = 24

export interface Session {
  name: string
  since: string
}

function read(): Session | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<Session>
    const name = typeof parsed.name === 'string' ? parsed.name.trim() : ''
    if (!name) return null
    return { name, since: typeof parsed.since === 'string' ? parsed.since : '' }
  } catch {
    return null
  }
}

export const session = ref<Session | null>(read())

/** Tidy a typed name: collapse spaces, trim, cap the length. */
export function cleanName(name: string): string {
  return name.replace(/\s+/g, ' ').trim().slice(0, MAX_NAME)
}

export function signIn(name: string): boolean {
  const clean = cleanName(name)
  if (!clean) return false
  const next: Session = { name: clean, since: new Date().toISOString() }
  session.value = next
  try {
    localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    // Signing in still works for this tab without storage.
  }
  return true
}

export function signOut(): void {
  session.value = null
  try {
    localStorage.removeItem(KEY)
  } catch {
    // Nothing to clear.
  }
}
