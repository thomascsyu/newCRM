/**
 * Pull a user-facing message from a form-script validate() failure.
 * Scripts may throw Error, frappe-ui objects with `messages`, or use throwError.
 */
export function getValidationErrorMessage(err) {
  if (!err) return __('Validation failed')
  if (err.alreadyToasted) return ''
  if (Array.isArray(err.messages) && err.messages[0]) return err.messages[0]
  if (typeof err.message === 'string' && err.message && err.message !== 'Error') {
    return err.message
  }
  return __('Validation failed')
}
