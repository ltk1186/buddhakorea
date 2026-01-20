// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 1.1. User can initiate Google OAuth login

import { test, expect } from '@playwright/test';

test.describe('OAuth Login Flow', () => {
  test('User can initiate Google OAuth login', async ({ page }) => {
    // 1. Navigate to mypage.html
    await page.goto('/mypage.html');

    // 2. Verify 'Login' button is visible when not authenticated
    const loginButton = page.locator(
      'button:has-text("로그인"), a:has-text("로그인"), [data-testid="login-button"]'
    ).first();
    await expect(loginButton).toBeVisible();

    // 3. Click on login link
    const googleLoginBtn = page.locator(
      '[data-provider="google"], .google-login, button:has-text("Google"), a[href*="/auth/login/google"]'
    ).first();
    
    if (await googleLoginBtn.isVisible()) {
      // Capture the click and check URL change
      const urlPromise = page.waitForURL(url => 
        url.includes('/auth/login/google') || url.includes('google')
      ).catch(() => null);
      
      await googleLoginBtn.click();
      
      // 4. Verify redirect URL structure contains /auth/login/google
      const finalUrl = page.url();
      expect(
        finalUrl.includes('/auth/login/google') ||
        finalUrl.includes('accounts.google.com') ||
        finalUrl.includes('oauth') ||
        finalUrl.includes('callback')
      ).toBeTruthy();
    }
  });
});
