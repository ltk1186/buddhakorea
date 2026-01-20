// spec: frontend/tests/specs/auth-login-test-plan.md
// scenario: 2.7. Responsive layout for mobile auth UI

import { test, expect } from '@playwright/test';

test.describe('Login UI & Session Management', () => {
  test('Responsive layout for mobile auth UI', async ({ page }) => {
    // 1. Set viewport to mobile (≤768px)
    await page.setViewportSize({ width: 375, height: 667 });

    // 2. Open mypage.html with login prompt
    await page.goto('/mypage.html');
    await page.waitForLoadState('networkidle');

    // 3. Verify login button is accessible
    const loginButton = page.locator(
      'button:has-text("로그인"), a:has-text("로그인"), [data-testid="login-button"]'
    ).first();
    
    await expect(loginButton).toBeVisible();
    
    // Check if button is within reasonable touch target size (at least 44x44px)
    const boundingBox = await loginButton.boundingBox();
    expect(boundingBox).toBeTruthy();
    if (boundingBox) {
      expect(boundingBox.width).toBeGreaterThanOrEqual(44);
      expect(boundingBox.height).toBeGreaterThanOrEqual(44);
    }

    // 4. Verify text sizes are readable
    const fontSize = await loginButton.evaluate(el => 
      window.getComputedStyle(el).fontSize
    );
    const fontSizePx = parseFloat(fontSize);
    expect(fontSizePx).toBeGreaterThanOrEqual(14); // Minimum readable font size

    // 5. Verify layout is not broken
    const viewportSize = page.viewportSize();
    const pageContent = page.locator('body');
    const contentWidth = await pageContent.evaluate(el => el.scrollWidth);
    
    // Content should not overflow
    expect(contentWidth).toBeLessThanOrEqual(viewportSize!.width + 20); // Allow small margin

    // 6. Set viewport to desktop
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.waitForTimeout(500);

    // 7. Verify layout adapts correctly
    const desktopContent = page.locator('body');
    const desktopContentWidth = await desktopContent.evaluate(el => el.scrollWidth);
    
    // Desktop layout should utilize more space
    expect(desktopContentWidth).toBeGreaterThan(viewportSize!.width);
  });
});
