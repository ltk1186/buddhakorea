// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 3.1. User can logout from mypage

import { test, expect } from '@playwright/test';

test.describe('Logout Functionality', () => {
  test('User can logout from mypage', async ({ page, context }) => {
    // 1. Log in user (simulate)
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_logout_token',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
      {
        name: 'refresh_token',
        value: 'test_refresh_logout',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 7 * 24 * 60 * 60 * 1000) / 1000),
      },
    ]);

    // 2. Navigate to mypage.html
    await page.goto('/mypage.html');
    await page.waitForLoadState('networkidle');

    // 3. Click logout button
    const logoutButton = page.locator(
      'button:has-text("로그아웃"), a:has-text("로그아웃"), [data-testid="logout-button"]'
    ).first();
    
    await expect(logoutButton).toBeVisible();

    // Intercept the logout request
    let logoutRequestMade = false;
    page.on('request', (request) => {
      if (request.url().includes('/auth/logout')) {
        logoutRequestMade = true;
      }
    });

    // 4. Verify logout POST request is sent to /auth/logout
    await logoutButton.click();
    await page.waitForTimeout(1000);

    expect(logoutRequestMade).toBe(true);

    // 5. Verify redirect to index.html
    await page.waitForLoadState('networkidle');
    const currentUrl = page.url();
    expect(currentUrl).toMatch(/index\.html|^\w+:\/\/[^\/]+\/?$/);
  });
});
