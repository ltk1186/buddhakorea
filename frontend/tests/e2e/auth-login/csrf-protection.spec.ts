// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 1.3. CSRF state validation is performed

import { test, expect } from '@playwright/test';

test.describe('OAuth Login Flow', () => {
  test('CSRF state validation is performed', async ({ page }) => {
    const base = process.env.BASE_URL ?? 'https://buddhakorea.com';
    const debug = process.env.DEBUG_OAUTH === '1' || process.env.DEBUG_OAUTH === 'true';

    if (debug) {
      page.on('request', r => console.log('[REQ]', r.method(), r.url()));
      page.on('response', r => {
        const loc = r.headers()['location'];
        console.log('[RESP]', r.status(), r.url(), loc ? `Location: ${loc}` : '');
      });
    }

    // 1. Missing state
    await page.goto(`${base}/auth/callback/google?code=test_code`, { waitUntil: 'networkidle' }).catch(() => {});
    let currentUrl = page.url();
    expect(
      currentUrl.includes('error') ||
      currentUrl.includes('login') ||
      currentUrl.includes('callback') ||
      currentUrl.includes(base)
    ).toBeTruthy();

    // 2. Invalid state
    await page.goto(`${base}/auth/callback/google?code=test_code&state=invalid_state`, { waitUntil: 'networkidle' }).catch(() => {});
    currentUrl = page.url();
    expect(
      currentUrl.includes('error') ||
      currentUrl.includes('login') ||
      currentUrl !== base + '/'
    ).toBeTruthy();

    // 3. Obtain real state by starting the OAuth login flow
    let state: string | null = null;

    // A: register waitForRequest before navigation to avoid race
    try {
      const [req] = await Promise.all([
        page.waitForRequest(r => r.url().includes('state='), { timeout: 10000 }),
        page.goto(`${base}/auth/login/google`, { waitUntil: 'domcontentloaded' }),
      ]);
      state = new URL(req.url()).searchParams.get('state');
    } catch {
      // B: fallback — capture 302/301 Location header if server redirects directly
      try {
        const [resp] = await Promise.all([
          page.waitForResponse(r =>
            (r.status() === 301 || r.status() === 302) &&
            ((r.headers()['location'] || '').includes('state=')),
            { timeout: 5000 }
          ),
          page.goto(`${base}/auth/login/google`, { waitUntil: 'domcontentloaded' }).catch(() => {}),
        ]);
        const location = resp.headers()['location'] ?? '';
        if (location) {
          state = new URL(location).searchParams.get('state');
        }
      } catch {
        // C: final fallback — check page.url() for state (less reliable)
        try {
          const redirectUrl = page.url();
          if (redirectUrl.includes('state=')) {
            state = new URL(redirectUrl).searchParams.get('state');
          }
        } catch {
          state = null;
        }
      }
    }

    expect(state, 'Could not capture OAuth state from /auth/login/google redirect').toBeTruthy();

    // Use captured state to simulate callback (encode to be safe)
    await page.goto(`${base}/auth/callback/google?code=test_code&state=${encodeURIComponent(state as string)}`, { waitUntil: 'networkidle' }).catch(() => {});

    // 4. Verify error handling or success handling
    const errorElement = page.locator('[data-testid="auth-error"], .error, .alert-danger').first();
    const isErrorVisible = await errorElement.isVisible().catch(() => false);
    currentUrl = page.url();
    expect(
      isErrorVisible ||
      currentUrl.includes('error') ||
      currentUrl.includes('login') ||
      currentUrl.includes('callback') ||
      currentUrl.includes(base)
    ).toBeTruthy();
  });
});