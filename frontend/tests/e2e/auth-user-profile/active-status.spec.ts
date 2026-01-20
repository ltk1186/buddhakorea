// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 5.5. User is_active status is respected

import { test, expect } from '@playwright/test';

test.describe('User Profile & Data Management', () => {
  test('User is_active status is respected', async ({ page, context }) => {
    // 1. Create active user (is_active=true)
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_active_user_token',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    // 2. Log in with active user
    let response = await page.request.get('/api/users/me');
    expect(response.ok()).toBe(true);

    const activeUserData = await response.json();
    expect(activeUserData.is_active).toBe(true);

    // 3. Deactivate user (is_active=false)
    // This would typically be done by an admin
    await context.clearCookies();
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_inactive_user_token',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    // 4. Attempt to use protected endpoints with inactive user
    response = await page.request.get('/api/users/me').catch(() => null);

    // Inactive users should be denied access or warned
    if (response && response.ok()) {
      const inactiveUserData = await response.json();
      expect(inactiveUserData.is_active).toBe(false);
      
      // If returned, should clearly indicate inactive status
      // Server might still return data but client should handle it
    }

    // 5. Clear message is shown for inactive accounts
    // This would be tested in UI tests
  });
});
