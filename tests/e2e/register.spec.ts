import { test, expect } from '@playwright/test';

test.describe('Register page', () => {
  test('renders form and fields and is interactive', async ({ page }) => {
    await page.goto('/register');

    // Suspense should resolve and show the client component
    await expect(page.getByRole('heading', { name: /register/i })).toBeVisible();

    // Fields
    await expect(page.locator('#invite')).toBeVisible();
    await expect(page.locator('#username')).toBeVisible();
    await expect(page.locator('#password')).toBeVisible();

    // Submit button
    const submit = page.getByRole('button', { name: /register/i });
    await expect(submit).toBeVisible();

    // Basic field interactions (no real submit)
    await page.locator('#invite').fill('sample-token');
    await page.locator('#username').fill('user1');
    await page.locator('#password').fill('pass1');

    await expect(page.locator('#invite')).toHaveValue('sample-token');
    await expect(page.locator('#username')).toHaveValue('user1');
    await expect(page.locator('#password')).toHaveValue('pass1');
  });
});
