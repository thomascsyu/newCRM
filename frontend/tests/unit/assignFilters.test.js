import {
  serializeAssignFilter,
  wrapAssignSearch,
} from '@/utils/assignFilters'

describe('wrapAssignSearch', () => {
  it('wraps a user id in percent wildcards', () => {
    expect(wrapAssignSearch('jane@gabriel.hk')).toBe('%jane@gabriel.hk%')
  })

  it('leaves an already-wrapped value alone', () => {
    expect(wrapAssignSearch('%jane%')).toBe('%jane%')
  })

  it('passes through empty values', () => {
    expect(wrapAssignSearch('')).toBe('')
    expect(wrapAssignSearch(null)).toBe(null)
  })
})

describe('serializeAssignFilter', () => {
  it('rewrites equals as LIKE', () => {
    expect(serializeAssignFilter('equals', 'jane@gabriel.hk')).toEqual([
      'LIKE',
      '%jane@gabriel.hk%',
    ])
  })

  it('rewrites = as LIKE', () => {
    expect(serializeAssignFilter('=', 'jane@gabriel.hk')).toEqual([
      'LIKE',
      '%jane@gabriel.hk%',
    ])
  })

  it('rewrites not equals as NOT LIKE', () => {
    expect(serializeAssignFilter('not equals', 'jane@gabriel.hk')).toEqual([
      'NOT LIKE',
      '%jane@gabriel.hk%',
    ])
  })

  it('returns null for operators that already work', () => {
    expect(serializeAssignFilter('like', 'jane')).toBeNull()
    expect(serializeAssignFilter('is', 'set')).toBeNull()
  })
})
