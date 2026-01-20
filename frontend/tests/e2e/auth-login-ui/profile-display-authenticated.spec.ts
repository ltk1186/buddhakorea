// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 2.2. User profile displays when authenticated

import { test, expect } from '@playwright/test';

test.describe('Login UI & Session Management', () => {
  test('User profile displays when authenticated', async ({ page, context }) => {
    // 1. Set authentication cookies (simulated login)
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_token_authenticated_user',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    // 2. Open mypage.html
    await page.goto('/mypage.html');
    await page.waitForLoadState('networkidle');

    // 3. Verify user nickname is displayed
    const userNickname = page.locator(
      '[data-testid="user-nickname"], .user-nickname, .profile-name'
    ).first();
    await expect(userNickname).toBeVisible();
    const nicknameText = await userNickname.textContent();
    expect(nicknameText).toBeTruthy();

    // 4. Verify logout button is visible
    const logoutButton = page.locator(
      'button:has-text("로그아웃"), a:has-text("로그아웃"), [data-testid="logout-button"]'
    ).first();
    await expect(logoutButton).toBeVisible();

    // 5. Verify login button is hidden
    const loginButton = page.locator(
      'button:has-text("로그인"), a:has-text("로그인"), [data-testid="login-button"]'
    ).first();
    const isLoginVisible = await loginButton.isVisible().catch(() => false);
    expect(isLoginVisible).toBe(false);
  });
});
