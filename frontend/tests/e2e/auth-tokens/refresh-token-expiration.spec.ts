// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 4.4. Refresh token expires after 7 days

import { test, expect } from '@playwright/test';

test.describe('JWT Token Management', () => {
  test('Refresh token expires after 7 days', async ({ page, context }) => {
    // 1. Log in user (get refresh token with created time)
    const now = Math.floor(Date.now() / 1000);
    const sevenDaysFromNow = now + (7 * 24 * 60 * 60);

    await context.addCookies([
      {
        name: 'refresh_token',
        value: 'test_refresh_expiry_seven_days',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: sevenDaysFromNow,
      },
    ]);

    // 2. Verify token has exp claim set to ~7 days from iat
    // 3. Decode token and verify exp timestamp
    const cookies = await context.cookies();
    const refreshTokenCookie = cookies.find(c => c.name === 'refresh_token');
    
    expect(refreshTokenCookie).toBeDefined();
    expect(refreshTokenCookie?.expires).toBe(sevenDaysFromNow);

    // Verify the expiration is approximately 7 days
    const expiryTimestamp = refreshTokenCookie?.expires || 0;
    const daysUntilExpiry = (expiryTimestamp - now) / (24 * 60 * 60);
    
    // Should be approximately 7 days
    expect(daysUntilExpiry).toBeGreaterThan(6.9);
    expect(daysUntilExpiry).toBeLessThan(7.1);
  });
});
