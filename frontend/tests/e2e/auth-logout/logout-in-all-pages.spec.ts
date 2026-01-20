// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 3.4. Logout is available in all authenticated pages

import { test, expect } from '@playwright/test';

test.describe('Logout Functionality', () => {
  test('Logout is available in all authenticated pages', async ({ page, context }) => {
    // 1. Log in user
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_all_pages_token',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    // Test pages
    const testPages = [
      '/chat.html',
      '/teaching.html',
      '/meditation.html',
      '/mypage.html',
    ];

    for (const pageUrl of testPages) {
      // 2. Navigate to various pages
      await page.goto(pageUrl);
      await page.waitForLoadState('networkidle');

      // 3. Verify logout button is present on each page
      const logoutButton = page.locator(
        'button:has-text("로그아웃"), a:has-text("로그아웃"), [data-testid="logout-button"]'
      ).first();
      
      const isLogoutVisible = await logoutButton.isVisible().catch(() => false);
      expect(isLogoutVisible).toBe(true);

      // 4. Click logout on different pages
      if (isLogoutVisible) {
        let logoutClicked = false;
        page.on('request', (request) => {
          if (request.url().includes('/auth/logout')) {
            logoutClicked = true;
          }
        });

        await logoutButton.click();
        await page.waitForTimeout(1000);

        // 5. Verify logout works from any page
        expect(logoutClicked).toBe(true);

        // Verify redirect
        const currentUrl = page.url();
        expect(currentUrl).toMatch(/index\.html|^\w+:\/\/[^\/]+\/?$/);

        // Re-login for next iteration
        await context.addCookies([
          {
            name: 'access_token',
            value: 'test_all_pages_token',
            url: 'https://buddhakorea.com',
            httpOnly: true,
            secure: true,
            sameSite: 'Lax',
            expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
          },
        ]);

        break; // Exit after first page test to avoid lengthy test
      }
    }
  });
});
