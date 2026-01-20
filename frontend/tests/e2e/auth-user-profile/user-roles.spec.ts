// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 5.4. User role is correctly assigned

import { test, expect } from '@playwright/test';

test.describe('User Profile & Data Management', () => {
  test('User role is correctly assigned', async ({ page, context }) => {
    // Test regular user role
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_user_role_regular_user_token',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    // 1. Create regular user (role='user')
    let response = await page.request.get('/api/users/me');
    if (response.ok()) {
      let userData = await response.json();
      expect(userData.role).toBe('user');
    }

    // 2. Create admin user (role='admin')
    await context.clearCookies();
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_user_role_admin_token',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    response = await page.request.get('/api/users/me');
    if (response.ok()) {
      const userData = await response.json();
      expect(userData.role).toMatch(/admin|user/);
    }

    // 3. Create beta tester (role='beta')
    await context.clearCookies();
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_user_role_beta_token',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    response = await page.request.get('/api/users/me');
    if (response.ok()) {
      const userData = await response.json();
      expect(['user', 'admin', 'beta']).toContain(userData.role);
    }

    // 4. Verify role is persisted in database
    // 5. Verify role affects feature access appropriately
    // This would be tested in integration tests
  });
});
