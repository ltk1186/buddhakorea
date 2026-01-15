import { defineConfig, devices } from '@playwright/test';

/**
 * Buddha Korea E2E Test Configuration
 *
 * 로컬 테스트: npm test
 * UI 모드: npm run test:ui
 * 브라우저 표시: npm run test:headed
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,

  reporter: [
    ['html', { open: 'never' }],
    ['list'],
  ],

  use: {
    // 프로덕션 서버 테스트
    baseURL: 'https://buddhakorea.com',

    // 실패 시 증거 수집
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',

    // 한국어 환경
    locale: 'ko-KR',
    timezoneId: 'Asia/Seoul',

    // 타임아웃 설정
    actionTimeout: 10000,
    navigationTimeout: 30000,
  },

  // 글로벌 타임아웃 (SSE 스트리밍 응답 대기)
  timeout: 60000,
  expect: {
    timeout: 10000,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'mobile',
      use: { ...devices['iPhone 13'] },
    },
  ],
});
