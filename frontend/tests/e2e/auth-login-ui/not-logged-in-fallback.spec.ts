// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 2.4. Not logged in state displays fallback

import { test, expect } from '@playwright/test';

test.describe('Login UI & Session Management', () => {
  test('Not logged in state displays fallback', async ({ page }) => {
    // 1. Open mypage.html without authentication
    await page.goto('/mypage.html');

    // 2. Wait for fetch to complete
    await page.waitForLoadState('networkidle');

    // 3. Verify not-logged-in card is displayed
    const notLoggedInCard = page.locator(
      '[data-testid="not-logged-in"], .not-logged-in, .login-required, [data-testid="login-fallback"]'
    ).first();
    
    await expect(notLoggedInCard).toBeVisible();

    // 4. Verify login button is visible
    const loginButton = page.locator(
      'button:has-text("로그인"), a:has-text("로그인"), [data-testid="login-button"]'
    ).first();
    
    await expect(loginButton).toBeVisible();

    // 5. Verify navigation back to home works
    const homeLink = page.locator(
      'a:has-text("홈"), a[href="/"], a[href*="index.html"], [data-testid="home-link"]'
    ).first();
    
    if (await homeLink.isVisible()) {
      await homeLink.click();
      await page.waitForLoadState('networkidle');
      
      // Verify we're on homepage
      const homeUrl = page.url();
      expect(homeUrl).toMatch(/index\.html|^\w+:\/\/[^\/]+\/?$/);
    }
  });
});
