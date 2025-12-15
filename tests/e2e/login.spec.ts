import { test, expect } from '@playwright/test';

test.describe('Login page', () => {
  test('renders form and navigation link', async ({ page }) => {
    await page.goto('/login');

    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible();

    await expect(page.locator('#username')).toBeVisible();
    await expect(page.locator('#password')).toBeVisible();

    const submit = page.getByRole('button', { name: /sign in/i });
    await expect(submit).toBeVisible();

    // Link to register
    const registerLink = page.getByRole('link', { name: /register/i });
    await expect(registerLink).toBeVisible();
    await expect(registerLink).toHaveAttribute('href', '/register');
  });
});
