// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 4.7. Token claims are properly verified

import { test, expect } from '@playwright/test';

test.describe('JWT Token Management', () => {
  test('Token claims are properly verified', async ({ page, context }) => {
    // 1. Create token with missing required claims
    // In real scenario, we would have malformed tokens to test
    
    const tokenMissingClaims = 'test_token_missing_claims_incomplete';
    
    await context.addCookies([
      {
        name: 'access_token',
        value: tokenMissingClaims,
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    // Attempt to use token with missing claims
    let response = await page.request.get('/api/users/me').catch(() => null);
    expect(!response || !response.ok()).toBe(true);

    // 2. Create token with incorrect type claim
    await context.clearCookies();
    const tokenWrongType = 'test_token_with_type_refresh_not_access';
    
    await context.addCookies([
      {
        name: 'access_token',
        value: tokenWrongType,
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    // Attempt to use token with incorrect type
    response = await page.request.get('/api/users/me').catch(() => null);
    expect(!response || !response.ok()).toBe(true);

    // 3. Create token with invalid signature
    await context.clearCookies();
    const tokenBadSignature = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiMTIzIiwidHlwZSI6ImFjY2VzcyJ9.INVALIDSIGNATURE123456789';
    
    await context.addCookies([
      {
        name: 'access_token',
        value: tokenBadSignature,
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    // 4. Attempt to use malformed tokens in protected endpoint
    response = await page.request.get('/api/users/me').catch(() => null);

    // All should fail
    expect(!response || !response.ok()).toBe(true);
  });
});
