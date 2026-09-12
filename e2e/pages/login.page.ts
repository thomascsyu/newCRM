import { Page, expect } from '@playwright/test'

export class LoginPage {
  constructor(private page: Page) {}
  async goto() { await this.page.goto('/company-login') }
  async expectOnLoginPage() {
    await expect(this.page.getByRole('link', { name: 'Sign in with Google' })).toBeVisible()
  }
}
