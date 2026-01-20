// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 1.8. User can view profile after login

import { test, expect } from '@playwright/test';

test.describe('OAuth Login Flow', () => {
  test('User can view profile after login', async ({ page, context }) => {
    // 1. Simulate successful OAuth login
    await context.addInitScript(() => {
      window.mockAuthenticatedUser = {
        id: 'user_profile_101',
        email: 'profile@example.com',
        nickname: 'ProfileUser',
        profile_img: null,
        is_active: true,
        created_at: new Date().toISOString(),
        last_login: new Date().toISOString(),
      };
    });

    // Set authentication cookies
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_token_value_12345',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
      {
        name: 'refresh_token',
        value: 'test_refresh_token_12345',
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

    // 3. Verify user information is displayed
    const userNickname = page.locator('[data-testid="user-nickname"], .user-nickname, .profile-name').first();
    const userEmail = page.locator('[data-testid="user-email"], .user-email, .profile-email').first();
    
    await expect(userNickname).toBeVisible();
    const nicknameText = await userNickname.textContent();
    expect(nicknameText).toBeTruthy();

    // 4. Verify usage statistics are shown
    const usageStats = page.locator('[data-testid="usage-stats"], .daily-limit, .usage-count').first();
    const hasUsageStats = await usageStats.isVisible().catch(() => false);
    expect(hasUsageStats).toBeTruthy();

    // 5. Verify logout option is available
    const logoutButton = page.locator(
      'button:has-text("로그아웃"), a:has-text("로그아웃"), [data-testid="logout-button"]'
    ).first();
    await expect(logoutButton).toBeVisible();
  });
});
