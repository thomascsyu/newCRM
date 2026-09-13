import { test, expect } from '@playwright/test'

test('shows only company Google sign-in', async ({ page }) => {
  await page.goto('/company-login')
  await expect(page.getByRole('link', { name: 'Sign in with Google' })).toBeVisible()
  await expect(page.locator('input[type=password]')).toHaveCount(0)
})

test('rejects password and API-token authentication', async ({ request }) => {
  const password = await request.post('/api/method/login', {
    form: { usr: 'Administrator', pwd: 'not-a-real-password' },
  })
  expect(password.ok()).toBeFalsy()
  const token = await request.get('/api/method/frappe.auth.get_logged_user', {
    headers: { Authorization: 'token invalid:invalid' },
  })
  expect(token.ok()).toBeFalsy()
})

test('rejects anonymous CRM data requests and forged callbacks', async ({ request }) => {
  expect((await request.get('/api/resource/CRM Lead')).ok()).toBeFalsy()
  const callback = await request.get('/api/method/crm.company_auth.callback?state=forged&code=forged', {
    maxRedirects: 0,
  })
  expect([301, 302, 303, 307, 308]).toContain(callback.status())
  expect(callback.headers()['location'] || '').toContain('/company-login')
})
