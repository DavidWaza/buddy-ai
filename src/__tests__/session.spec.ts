import { beforeEach, describe, expect, it } from 'vitest'
import { cleanName, session, signIn, signOut } from '../session'

describe('dummy session', () => {
  beforeEach(() => {
    localStorage.clear()
    signOut()
  })

  it('signs in with the typed name and remembers it', () => {
    expect(signIn('  Ada   Lovelace ')).toBe(true)
    expect(session.value?.name).toBe('Ada Lovelace')
    expect(JSON.parse(localStorage.getItem('buddy-ai:user') ?? '{}').name).toBe('Ada Lovelace')
  })

  it('refuses an empty name', () => {
    expect(signIn('   ')).toBe(false)
    expect(session.value).toBeNull()
  })

  it('signs out and forgets the name', () => {
    signIn('Favour')
    signOut()
    expect(session.value).toBeNull()
    expect(localStorage.getItem('buddy-ai:user')).toBeNull()
  })

  it('caps very long names', () => {
    expect(cleanName('x'.repeat(50))).toHaveLength(24)
  })
})
