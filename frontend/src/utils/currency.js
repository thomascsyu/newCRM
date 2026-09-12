/**
 * Resolve the currency code for a Currency field's `options`.
 *
 * Desk formats:
 *   - `currency` — fieldname on this doc (or parent)
 *   - `currency:Company` — fieldname, with a parent/link hint
 *   - `Company:company:default_currency` — value on a linked doctype
 *
 * List formatters are sync, so linked-doc lookups use values already on
 * the current/parent doc. Missing values fall back to the system default.
 */
export function resolveCurrency(
  options,
  doc,
  parentDoc = null,
  fallback = 'USD',
) {
  const defaultCurrency = fallback || 'USD'
  if (!options || typeof options !== 'string') return defaultCurrency

  const read = (fieldname) => {
    if (fieldname && doc && doc[fieldname]) return doc[fieldname]
    if (fieldname && parentDoc && parentDoc[fieldname]) return parentDoc[fieldname]
    return null
  }

  if (!options.includes(':')) {
    return read(options) || defaultCurrency
  }

  const parts = options
    .split(':')
    .map((part) => part.trim())
    .filter(Boolean)

  if (parts.length === 3) {
    const [, linkField, sourceField] = parts
    return (
      read(sourceField) ||
      read(`${linkField}_${sourceField}`) ||
      defaultCurrency
    )
  }

  if (parts.length === 2) {
    const [fieldname] = parts
    return read(fieldname) || defaultCurrency
  }

  return defaultCurrency
}
