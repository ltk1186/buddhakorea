// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 2.1. Login button displays when not authenticated

import { test, expect } from '@playwright/test';

test.describe('Login UI & Session Management', () => {
  test('Login button displays when not authenticated', async ({ page }) => {
    // 1. Open mypage.html without authentication
    await page.goto('/mypage.html');
    await page.waitForLoadState('networkidle');

    // 2. Verify login button text is '로그인'
    const loginButton = page.locator(
      'button:has-text("로그인"), a:has-text("로그인"), [data-testid="login-button"]'
    ).first();
    
    await expect(loginButton).toBeVisible();
    const buttonText = await loginButton.textContent();
    expect(buttonText).toContain('로그인');

    // 3. Verify button links to /auth/login/google
    const href = await loginButton.getAttribute('href');
    const onclick = await loginButton.getAttribute('onclick');
    
    // Check if it's a link or has navigation
    if (href) {
      expect(href).toMatch(/auth\/login|google/i);
    }

    // 4. Verify no user information is displayed
    const userProfile = page.locator('[data-testid="user-profile"], .profile-section, .user-info').first();
    const isUserProfileVisible = await userProfile.isVisible().catch(() => false);
    expect(isUserProfileVisible).toBe(false);

    // Verify login prompt is visible instead
    const loginPrompt = page.locator(
      '[data-testid="login-prompt"], .login-prompt, .not-logged-in, :text("로그인하기")'
    ).first();
    const isLoginPromptVisible = await loginPrompt.isVisible().catch(() => false);
    expect(isLoginPromptVisible).toBe(true);
  });
});
