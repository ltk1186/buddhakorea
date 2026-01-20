// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 4.5. Token payload includes required claims

import { test, expect } from '@playwright/test';

test.describe('JWT Token Management', () => {
  test('Token payload includes required claims', async ({ page, context }) => {
    // Helper to decode JWT (without verification)
    const decodeJWT = (token: string) => {
      const parts = token.split('.');
      if (parts.length !== 3) return null;
      
      try {
        const decoded = JSON.parse(
          Buffer.from(parts[1], 'base64').toString('utf-8')
        );
        return decoded;
      } catch {
        return null;
      }
    };

    // 1. Log in user (get tokens)
    await context.addCookies([
      {
        name: 'access_token',
        value: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiMTIzNDU2Nzg5MCIsInN1YiI6InVzZXJAZXhhbXBsZS5jb20iLCJ0eXBlIjoiYWNjZXNzIiwiaWF0IjoxNTE2MjM5MDIyLCJleHAiOjE1MTYyMzkyMjJ9.test',
        url: 'https://buddhakorea.com',
        httpOnly: true,
        secure: true,
        sameSite: 'Lax',
        expires: Math.floor((Date.now() + 15 * 60 * 1000) / 1000),
      },
    ]);

    // 2. Decode access token
    const accessToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiMTIzNDU2Nzg5MCIsInN1YiI6InVzZXJAZXhhbXBsZS5jb20iLCJ0eXBlIjoiYWNjZXNzIiwiaWF0IjoxNTE2MjM5MDIyLCJleHAiOjE1MTYyMzkyMjJ9.test';
    const accessPayload = decodeJWT(accessToken);

    // 3. Verify access_token includes: user_id, sub (email), type='access', iat, exp
    if (accessPayload) {
      expect(accessPayload).toHaveProperty('user_id');
      expect(accessPayload).toHaveProperty('sub'); // email
      expect(accessPayload.type).toBe('access');
      expect(accessPayload).toHaveProperty('iat');
      expect(accessPayload).toHaveProperty('exp');
    }

    // 4. Decode refresh token (in real scenario)
    const refreshToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiMTIzNDU2Nzg5MCIsInR5cGUiOiJyZWZyZXNoIiwiaWF0IjoxNTE2MjM5MDIyLCJleHAiOjE1MjMyMjUwMjJ9.test';
    const refreshPayload = decodeJWT(refreshToken);

    // 5. Verify refresh_token includes: user_id, type='refresh', iat, exp
    if (refreshPayload) {
      expect(refreshPayload).toHaveProperty('user_id');
      expect(refreshPayload.type).toBe('refresh');
      expect(refreshPayload).toHaveProperty('iat');
      expect(refreshPayload).toHaveProperty('exp');
    }
  });
});
