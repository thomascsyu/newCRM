import * as fs from 'fs'
import { expect, test as setup } from '@playwright/test'

const authFile = 'e2e/.auth/user.json'
setup('validate saved Google session', async ({ browser }) => {
  if (!fs.existsSync(authFile)) {
    throw new Error('Save a genuine Google-signed-in staging browser state to e2e/.auth/user.json first. See docs/zeabur-deployment.md.')
  }
  const context = await browser.newContext({ storageState: authFile, baseURL: process.env.BASE_URL || 'http://crm.test:8000' })
  const page = await context.newPage()
  try {
    const user = await page.request.get('/api/method/frappe.auth.get_logged_user')
    expect(user.ok()).toBeTruthy()
    expect((await user.json()).message).not.toBe('Guest')
    await page.goto('/crm')
    await page.waitForFunction(() => !!(window as any).csrf_token)
    const csrf = await page.evaluate(() => (window as any).csrf_token)
    fs.writeFileSync('e2e/.auth/csrf.json', JSON.stringify({ csrf_token: csrf }))
    await context.storageState({ path: authFile })
  } finally { await context.close() }
})
