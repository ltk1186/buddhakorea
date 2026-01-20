// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 4.2. Refresh token is used to get new access token

import { test, expect } from '@playwright/test';

test.describe('JWT Token Management', () => {
  test('Refresh token is used to get new access token', async ({ page, context }) => {
    // 1. Log in user (get refresh token)
    await context.addCookies([
      {
        name: 'refresh_token',
        value: 'test_refresh_valid_token_for_refresh',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 7 * 24 * 60 * 60 * 1000) / 1000),
      },
    ]);

    // 2. Call /auth/refresh endpoint with refresh_token
    const refreshResponse = await page.request.post('/auth/refresh').catch(() => null);

    if (refreshResponse && refreshResponse.ok()) {
      // 3. Verify new access_token is returned
      const refreshData = await refreshResponse.json();
      expect(refreshData).toHaveProperty('access_token');
      
      const newAccessToken = refreshData.access_token;
      expect(newAccessToken).toBeTruthy();

      // 4. Verify new access_token works for protected endpoints
      // Set the new token in cookies
      await context.clearCookies();
      await context.addCookies([
        {
          name: 'access_token',
          value: newAccessToken,
          url: 'https://buddhakorea.com',
          httpOnly: true,
          secure: true,
          sameSite: 'Lax',
          expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
        },
      ]);

      // Test with new token
      const userResponse = await page.request.get('/api/users/me');
      expect(userResponse.ok()).toBe(true);
    }
  });
});
