// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 3.2. Logout clears authentication cookies

import { test, expect } from '@playwright/test';

test.describe('Logout Functionality', () => {
  test('Logout clears authentication cookies', async ({ page, context }) => {
    // 1. Log in user (simulate with cookies)
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_cookie_clear_token',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
      {
        name: 'refresh_token',
        value: 'test_refresh_clear',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 7 * 24 * 60 * 60 * 1000) / 1000),
      },
    ]);

    // 2. Verify access_token cookie exists
    let cookies = await context.cookies();
    const accessTokenBefore = cookies.find(c => c.name === 'access_token');
    expect(accessTokenBefore).toBeDefined();

    // Navigate to mypage
    await page.goto('/mypage.html');
    await page.waitForLoadState('networkidle');

    // 3. Click logout button
    const logoutButton = page.locator(
      'button:has-text("로그아웃"), a:has-text("로그아웃"), [data-testid="logout-button"]'
    ).first();
    
    await expect(logoutButton).toBeVisible();
    await logoutButton.click();
    await page.waitForTimeout(1000);

    // 4. Verify access_token cookie is deleted
    cookies = await context.cookies();
    const accessTokenAfter = cookies.find(c => c.name === 'access_token');
    expect(accessTokenAfter).toBeUndefined();

    // 5. Verify refresh_token cookie is deleted
    const refreshTokenAfter = cookies.find(c => c.name === 'refresh_token');
    expect(refreshTokenAfter).toBeUndefined();
  });
});
