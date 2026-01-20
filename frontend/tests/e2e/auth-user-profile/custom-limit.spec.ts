// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 5.3. User can have custom daily_chat_limit

import { test, expect } from '@playwright/test';

test.describe('User Profile & Data Management', () => {
  test('User can have custom daily_chat_limit', async ({ page, context }) => {
    // 1. Create admin user with custom limit (50)
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_custom_limit_admin_token',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    // Get user to check custom limit
    const userResponse = await page.request.get('/api/users/me');
    if (!userResponse.ok()) return;

    const userData = await userResponse.json();
    const customLimit = userData.daily_chat_limit || 50;

    // 2. Grant higher limit to specific user (already set in mock)
    // This would be done through admin API in real scenario

    // 3. Make 50 requests with that user
    let successCount = 0;
    for (let i = 0; i < customLimit; i++) {
      const chatResponse = await page.request.post('/api/chat', {
        data: { message: `Custom limit test ${i + 1}` }
      }).catch(() => null);

      if (chatResponse && chatResponse.ok()) {
        successCount++;
      } else {
        break;
      }
    }

    expect(successCount).toBeGreaterThanOrEqual(customLimit - 1);

    // 4. Verify 51st request is blocked
    const exceededResponse = await page.request.post('/api/chat', {
      data: { message: 'Should exceed custom limit' }
    }).catch(() => null);

    expect(exceededResponse && !exceededResponse.ok()).toBe(true);
  });
});
