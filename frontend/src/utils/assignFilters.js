/**
 * `_assign` is stored as a JSON array string, e.g. `["jane@gabriel.hk"]`.
 * Exact equals/not-equals never match that payload, so those operators are
 * rewritten as LIKE / NOT LIKE against the user id.
 */

export function wrapAssignSearch(value) {
  if (value == null || value === '') return value
  const text = String(value)
  return text.includes('%') ? text : `%${text}%`
}

/**
 * @param {string} operator
 * @param {*} value
 * @returns {[string, *]|null} Frappe filter tuple, or null to use the default path
 */
export function serializeAssignFilter(operator, value) {
  const op = String(operator || '').toLowerCase()
  if (op === 'equals' || op === '=') {
    return ['LIKE', wrapAssignSearch(value)]
  }
  if (op === 'not equals' || op === '!=') {
    return ['NOT LIKE', wrapAssignSearch(value)]
  }
  return null
}
