import { resolveCurrency } from '@/utils/currency'

describe('resolveCurrency', () => {
  it('uses the system fallback when options are empty', () => {
    expect(resolveCurrency('', {}, null, 'USD')).toBe('USD')
    expect(resolveCurrency(null, { currency: 'HKD' }, null, 'USD')).toBe('USD')
  })

  it('reads a same-doc fieldname', () => {
    expect(resolveCurrency('currency', { currency: 'HKD' })).toBe('HKD')
  })

  it('reads the field from the parent document', () => {
    expect(
      resolveCurrency('currency', {}, { currency: 'EUR' }, 'USD'),
    ).toBe('EUR')
  })

  it('handles two-part options (field:Doctype)', () => {
    expect(
      resolveCurrency('currency:Company', { currency: 'GBP' }, null, 'USD'),
    ).toBe('GBP')
  })

  it('handles three-part options from the current doc', () => {
    expect(
      resolveCurrency(
        'Company:company:default_currency',
        { default_currency: 'JPY' },
        null,
        'USD',
      ),
    ).toBe('JPY')
  })

  it('handles three-part options from a denormalized link field', () => {
    expect(
      resolveCurrency(
        'Company:company:default_currency',
        { company_default_currency: 'SGD' },
        null,
        'USD',
      ),
    ).toBe('SGD')
  })

  it('falls back when the linked value is not on the row', () => {
    expect(
      resolveCurrency(
        'Company:company:default_currency',
        { company: 'Gabriel' },
        null,
        'USD',
      ),
    ).toBe('USD')
  })
})
