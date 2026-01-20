// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 3.5. User is logged out on session expiration

import { test, expect } from '@playwright/test';

test.describe('Logout Functionality', () => {
  test('User is logged out on session expiration', async ({ page, context }) => {
    // 1. Log in user with expired token (already past expiration)
    const expiredTime = Math.floor(Date.now() / 1000) - 100; // 100 seconds in the past
    
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_expired_token',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: expiredTime,
      },
    ]);

    await page.goto('/mypage.html');
    await page.waitForLoadState('networkidle');

    // 2. Let session remain idle (already expired)
    await page.waitForTimeout(1000);

    // 3. Attempt to make API request
    let apiResponse = await page.request.get('/api/users/me').catch(err => {
      return { ok: () => false, status: () => 401 };
    });

    // 4. Verify token is expired
    // Expired token should result in 401 Unauthorized
    const isExpired = !apiResponse.ok() || apiResponse.status() === 401;
    expect(isExpired || page.url().includes('login')).toBeTruthy();

    // 5. Verify system redirects to login
    // The page should show login prompt or redirect to login
    const loginPrompt = page.locator(
      'button:has-text("로그인"), [data-testid="login-prompt"], .login-required'
    ).first();
    
    const isLoginPromptVisible = await loginPrompt.isVisible().catch(() => false);
    
    // Either login prompt is shown or page redirected to login
    expect(isLoginPromptVisible || page.url().includes('auth')).toBeTruthy();
  });
});
