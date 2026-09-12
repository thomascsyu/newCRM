import { getValidationErrorMessage } from '@/utils/validationError'

describe('getValidationErrorMessage', () => {
  it('returns a default for a missing error', () => {
    expect(getValidationErrorMessage(null)).toBe('Validation failed')
  })

  it('prefers frappe-ui messages', () => {
    expect(
      getValidationErrorMessage({ messages: ['Name is required'] }),
    ).toBe('Name is required')
  })

  it('uses Error.message', () => {
    expect(getValidationErrorMessage(new Error('Stop'))).toBe('Stop')
  })

  it('skips errors that were already toasted', () => {
    const err = new Error('Already shown')
    err.alreadyToasted = true
    expect(getValidationErrorMessage(err)).toBe('')
  })
})
