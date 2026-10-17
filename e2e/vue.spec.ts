import { test, expect } from '@playwright/test'

test('signs in and greets by the typed name', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Your name').fill('Ada')
  await page.getByRole('button', { name: 'Start talking' }).click()

  await expect(page.locator('h1')).toHaveText("Let's talk, Ada")

  await page.getByRole('button', { name: 'Start talking' }).click()
  await expect(page.getByRole('button', { name: 'Finish speaking' })).toBeVisible()
})

test('signing out returns to the login screen', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Your name').fill('Ada')
  await page.getByRole('button', { name: 'Start talking' }).click()
  await expect(page.locator('h1')).toHaveText("Let's talk, Ada")

  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page.getByLabel('Your name')).toBeVisible()
})
