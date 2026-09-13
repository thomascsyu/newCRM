import { describe, expect, it } from 'vitest'
import {
  cookieUserId,
  verifiedSessionUser,
} from '@/utils/sessionUser'

describe('cookieUserId', () => {
  it('returns the user_id cookie when present', () => {
    expect(cookieUserId('sid=abc; user_id=rep@company.test')).toBe(
      'rep@company.test',
    )
  })

  it('treats Guest as logged out', () => {
    expect(cookieUserId('user_id=Guest')).toBeNull()
  })
})

describe('verifiedSessionUser', () => {
  it('requires the server Google login marker to match', () => {
    const cookie = 'user_id=rep@company.test'
    expect(
      verifiedSessionUser(cookie, 'rep@company.test'),
    ).toBe('rep@company.test')
    expect(verifiedSessionUser(cookie, null)).toBeNull()
    expect(verifiedSessionUser(cookie, 'other@company.test')).toBeNull()
  })
})
