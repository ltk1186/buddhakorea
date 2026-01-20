// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 5.6. User last_login is updated on each login

import { test, expect } from '@playwright/test';

test.describe('User Profile & Data Management', () => {
  test('User last_login is updated on each login', async ({ page, context }) => {
    // 1. Create user and note last_login timestamp
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_last_login_token_first_time',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    let response = await page.request.get('/api/users/me');
    const firstLoginData = await response.json();
    const firstLastLogin = new Date(firstLoginData.last_login);

    // 2. Log out user
    await context.clearCookies();

    // 3. Wait a few seconds
    await page.waitForTimeout(2000);

    // 4. Log in again
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_last_login_token_second_time',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    response = await page.request.get('/api/users/me');
    const secondLoginData = await response.json();
    const secondLastLogin = new Date(secondLoginData.last_login);

    // 5. Verify last_login is updated to new time
    expect(secondLastLogin.getTime()).toBeGreaterThan(firstLastLogin.getTime());

    // Timestamp should reflect actual login time (within reasonable margin)
    const timeDiff = secondLastLogin.getTime() - firstLastLogin.getTime();
    expect(timeDiff).toBeGreaterThan(1500); // At least 1.5 seconds
    expect(timeDiff).toBeLessThan(5000); // But not more than 5 seconds
  });
});
