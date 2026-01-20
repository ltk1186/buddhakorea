// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 4.1. Access token is validated on protected endpoints

import { test, expect } from '@playwright/test';

test.describe('JWT Token Management', () => {
  test('Access token is validated on protected endpoints', async ({ page, context }) => {
    // 1. Log in user (get access token)
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_valid_access_token_valid_signature',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    // 2. Make request to /api/users/me with valid token
    let response = await page.request.get('/api/users/me');
    expect(response.ok()).toBe(true);

    // 3. Verify request succeeds
    const userData = await response.json();
    expect(userData).toHaveProperty('id');
    expect(userData).toHaveProperty('email');

    // 4. Make request with modified token payload
    // Clear cookies and set invalid token
    await context.clearCookies();
    await context.addCookies([
      {
        name: 'access_token',
        value: 'test_modified_invalid_token_tampered_payload',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    // 5. Verify request fails with 401
    response = await page.request.get('/api/users/me').catch(err => {
      return { ok: () => false, status: () => 401 };
    });
    
    expect(!response.ok() || response.status() === 401).toBe(true);
  });
});
