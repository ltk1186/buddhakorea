// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 5.8. User data is persisted across sessions

import { test, expect } from '@playwright/test';

test.describe('User Profile & Data Management', () => {
  test('User data is persisted across sessions', async ({ page, context, browser }) => {
    // 1. Log in and create user session
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_persistence_token_session_1',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    let response = await page.request.get('/api/users/me');
    const userData1 = await response.json();

    // Store user data to compare later
    const originalUserId = userData1.id;
    const originalEmail = userData1.email;
    const originalNickname = userData1.nickname;

    // 2. Close browser/session
    await page.close();

    // 3. Log in again with same credentials
    const newContext = await browser.newContext();
    const newPage = await newContext.newPage();

    await newContext.addCookies([
      {
        name: 'access_token',
        value: 'test_persistence_token_session_2',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    // 4. Verify all user data is intact
    response = await newPage.request.get('/api/users/me');
    const userData2 = await response.json();

    expect(userData2.id).toBe(originalUserId);
    expect(userData2.email).toBe(originalEmail);
    expect(userData2.nickname).toBe(originalNickname);

    // Verify all fields are still present
    expect(userData2).toHaveProperty('created_at');
    expect(userData2).toHaveProperty('last_login');
    expect(userData2).toHaveProperty('role');
    expect(userData2).toHaveProperty('is_active');

    await newContext.close();
  });
});
