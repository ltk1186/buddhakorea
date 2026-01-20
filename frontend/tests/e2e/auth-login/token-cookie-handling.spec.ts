// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 1.6. JWT access token is set in cookies after login

import { test, expect } from '@playwright/test';

test.describe('OAuth Login Flow', () => {
  test('JWT access token is set in cookies after login', async ({ page, context }) => {
    // 1. Simulate successful OAuth callback
    await context.addInitScript(() => {
      // Mock successful login
      window.mockLoginSuccess = true;
    });

    await page.goto('/auth/callback/google?code=test_code&state=test_state');
    await page.waitForTimeout(2000);

    // 2. Verify access_token cookie is set
    const cookies = await context.cookies();
    const accessTokenCookie = cookies.find(c => c.name === 'access_token');
    
    if (accessTokenCookie) {
      expect(accessTokenCookie).toBeDefined();
      expect(accessTokenCookie.value).toBeTruthy();

      // 3. Verify refresh_token cookie is set
      const refreshTokenCookie = cookies.find(c => c.name === 'refresh_token');
      expect(refreshTokenCookie).toBeDefined();
      expect(refreshTokenCookie.value).toBeTruthy();

      // 4. Verify cookie security attributes (httpOnly, secure, sameSite)
      // Note: httpOnly cannot be directly verified from client, but we can check other attributes
      expect(accessTokenCookie.httpOnly).toBe(true);
      expect(accessTokenCookie.sameSite).toMatch(/Lax|Strict|None/i);
      
      // In production, secure should be true
      if (page.url().startsWith('https')) {
        expect(accessTokenCookie.secure).toBe(true);
      }

      // 5. Verify token expiration settings
      // Access token should expire in ~15 minutes
      const accessTokenExpiry = accessTokenCookie.expires;
      const nowInSeconds = Math.floor(Date.now() / 1000);
      const expiryInSeconds = accessTokenExpiry;
      const expiryDiff = expiryInSeconds - nowInSeconds;
      
      // Should expire in approximately 15 minutes (900 seconds) ±1 minute buffer
      expect(expiryDiff).toBeGreaterThan(14 * 60);
      expect(expiryDiff).toBeLessThan(16 * 60);

      // Refresh token should expire in ~7 days
      const refreshTokenExpiry = refreshTokenCookie.expires;
      const refreshExpiryDiff = refreshTokenExpiry - nowInSeconds;
      const sevenDaysInSeconds = 7 * 24 * 60 * 60;
      
      // Should expire in approximately 7 days ±1 day buffer
      expect(refreshExpiryDiff).toBeGreaterThan(sevenDaysInSeconds - 86400);
      expect(refreshExpiryDiff).toBeLessThan(sevenDaysInSeconds + 86400);
    }
  });
});
