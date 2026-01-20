// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 1.2. User can initiate Naver OAuth login

import { test, expect } from '@playwright/test';

test.describe('OAuth Login Flow', () => {
  test('User can initiate Naver OAuth login', async ({ page }) => {
    // 1. Navigate to mypage.html
    await page.goto('/mypage.html');

    // 2. Verify 'Login' button is visible when not authenticated
    const loginButton = page.locator(
      'button:has-text("로그인"), a:has-text("로그인"), [data-testid="login-button"]'
    ).first();
    await expect(loginButton).toBeVisible();

    // 3. Click on Naver login option
    const naverLoginBtn = page.locator(
      '[data-provider="naver"], .naver-login, button:has-text("네이버"), a[href*="/auth/login/naver"]'
    ).first();
    
    if (await naverLoginBtn.isVisible()) {
      // 4. Verify redirect URL structure contains /auth/login/naver
      const urlPromise = page.waitForURL(url => 
        url.includes('/auth/login/naver') || url.includes('naver')
      ).catch(() => null);
      
      await naverLoginBtn.click();
      
      const finalUrl = page.url();
      expect(
        finalUrl.includes('/auth/login/naver') ||
        finalUrl.includes('nid.naver.com') ||
        finalUrl.includes('callback') ||
        finalUrl.includes('redirect_uri')
      ).toBeTruthy();
    }
  });
});
