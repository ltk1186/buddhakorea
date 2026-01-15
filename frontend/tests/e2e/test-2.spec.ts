import { test, expect } from '@playwright/test';

test('test', async ({ page }) => {
  await page.goto('https://civitai.com/');
  await page.getByRole('link', { name: 'images', exact: true }).click();
  await page.getByRole('link').filter({ hasText: /^$/ }).nth(1).click();
  await page.locator('.mantine-focus-auto.mantine-active.size-9').click();
  await page.locator('div:nth-child(2) > div:nth-child(7) > .CosmeticWrapper_wrapper__kH8WX > .relative.flex > .relative > .mantine-focus-auto.m_849cf0da').click();
  await page.locator('.mantine-focus-auto.mantine-active.size-9').click();
});