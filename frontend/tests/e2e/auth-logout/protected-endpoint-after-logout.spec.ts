// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 3.3. User cannot access protected endpoints after logout

import { test, expect } from '@playwright/test';

test.describe('Logout Functionality', () => {
  test('User cannot access protected endpoints after logout', async ({ page, context }) => {
    // 1. Log in and set session
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_protected_token',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    await page.goto('/mypage.html');
    await page.waitForLoadState('networkidle');

    // 2. Access /api/users/me (should succeed)
    let response = await page.request.get('/api/users/me');
    expect(response.ok()).toBe(true);

    // 3. Log out
    const logoutButton = page.locator(
      'button:has-text("로그아웃"), a:has-text("로그아웃"), [data-testid="logout-button"]'
    ).first();
    
    await logoutButton.click();
    await page.waitForTimeout(1000);

    // 4. Attempt to access /api/users/me again
    response = await page.request.get('/api/users/me').catch(err => err);

    // 5. Verify 401 or 403 response
    // After logout, the request should fail due to missing/invalid token
    if (response && response.ok) {
      // If request somehow succeeds, it should not be with valid user data
      expect(response.ok()).toBe(false);
    } else {
      // Expected behavior - request fails
      expect(response).toBeDefined();
    }
  });
});
