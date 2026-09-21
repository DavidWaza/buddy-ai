import { test, expect } from '@playwright/test'

test('shows the greeting and starts listening from the mic', async ({ page }) => {
  await page.goto('/?name=Favour')
  await expect(page.locator('h1')).toHaveText("Let's talk, Favour")
  await page.getByRole('button', { name: 'Start talking' }).click()
  await expect(page.getByRole('button', { name: 'Finish speaking' })).toBeVisible()
})
