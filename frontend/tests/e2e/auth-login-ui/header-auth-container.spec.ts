// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 2.6. Auth container updates dynamically on header

import { test, expect } from '@playwright/test';

test.describe('Login UI & Session Management', () => {
  test('Auth container updates dynamically on header', async ({ page, context }) => {
    // 1. Open any page with header (index.html)
    await page.goto('/index.html');
    await page.waitForLoadState('networkidle');

    // 2. Verify auth container shows login link
    const authContainer = page.locator(
      '[data-testid="auth-container"], .auth-container, .header-auth'
    ).first();
    
    await expect(authContainer).toBeVisible();

    const loginLink = authContainer.locator(
      'a:has-text("로그인"), button:has-text("로그인")'
    );
    
    const isLoginVisible = await loginLink.isVisible().catch(() => false);
    expect(isLoginVisible).toBe(true);

    // 3. Simulate authentication by setting cookies
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_dynamic_token',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    // Reload page to see updated auth state
    await page.reload();
    await page.waitForLoadState('networkidle');

    // 4. Verify auth container updates to show username
    const userNameDisplay = authContainer.locator(
      '[data-testid="user-name"], .username, .user-nickname'
    ).first();
    
    const isUserNameVisible = await userNameDisplay.isVisible().catch(() => false);
    expect(isUserNameVisible).toBe(true);

    // 5. Verify logout link is present
    const logoutLink = authContainer.locator(
      'a:has-text("로그아웃"), button:has-text("로그아웃"), [data-testid="logout-btn"]'
    ).first();
    
    const isLogoutVisible = await logoutLink.isVisible().catch(() => false);
    expect(isLogoutVisible).toBe(true);
  });
});
