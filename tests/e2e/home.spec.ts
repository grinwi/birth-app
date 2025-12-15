import { test, expect } from '@playwright/test';

test.describe('Home page', () => {
  test('loads and renders core UI', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('h1', { hasText: 'Birthdays App' })).toBeVisible();
    await expect(page.locator('#backend-status')).toBeVisible();
    await expect(page.locator('table#birthdays-table')).toBeVisible();

    // Top controls
    await expect(page.locator('#save-github-btn')).toBeVisible();
    await expect(page.locator('#set-api-base-btn')).toBeVisible();
  });

  test('has filter and sorting controls', async ({ page }) => {
    await page.goto('/');

    // Filters
    const filterIds = [
      '#all-btn',
      '#today-btn',
      '#this-week-btn',
      '#next-week-btn',
      '#this-month-btn',
      '#next-month-btn',
      '#this-quarter-btn',
      '#next-quarter-btn',
      '#this-year-btn',
      '#next-year-btn'
    ];
    for (const id of filterIds) {
      await expect(page.locator(id)).toBeVisible();
    }

    // Sorting buttons by column
    const sortIds = [
      '#sort-first-name-btn',
      '#sort-last-name-btn',
      '#sort-day-btn',
      '#sort-month-btn',
      '#sort-year-btn',
      '#sort-age-btn'
    ];
    for (const id of sortIds) {
      await expect(page.locator(id)).toBeVisible();
    }
  });
});
