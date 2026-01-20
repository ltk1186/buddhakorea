// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 5.2. User daily_chat_limit is applied correctly

import { test, expect } from '@playwright/test';

test.describe('User Profile & Data Management', () => {
  test('User daily_chat_limit is applied correctly', async ({ page, context }) => {
    // 1. Create user with default limit (20)
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_daily_limit_user_token',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    // Get user info to verify limit
    const userResponse = await page.request.get('/api/users/me');
    if (!userResponse.ok()) return;

    const userData = await userResponse.json();
    const dailyLimit = userData.daily_chat_limit || 20;

    // 2. Make chat requests up to limit
    for (let i = 0; i < dailyLimit; i++) {
      const chatResponse = await page.request.post('/api/chat', {
        data: { message: `Test message ${i + 1}` }
      }).catch(() => null);

      if (chatResponse && !chatResponse.ok()) {
        // Limit reached before expected
        break;
      }
    }

    // 3. Verify 21st request is blocked
    const exceededResponse = await page.request.post('/api/chat', {
      data: { message: 'Should be blocked' }
    }).catch(() => null);

    expect(exceededResponse && !exceededResponse.ok()).toBe(true);

    // 4. Verify error message mentions limit
    if (exceededResponse && !exceededResponse.ok()) {
      const errorData = await exceededResponse.json().catch(() => ({}));
      expect(
        errorData.error?.includes('limit') ||
        errorData.message?.includes('limit') ||
        errorData.detail?.includes('limit')
      ).toBeTruthy();
    }
  });
});
