import { test, expect } from '@playwright/test';

test('test', async ({ page }) => {
  await page.goto('https://buddhakorea.com/');
  await page.getByRole('link', { name: '더 알아보기' }).click();
  await page.getByRole('link', { name: 'AI 채팅 시작하기' }).click();
  await page.getByRole('button', { name: '라이브러리' }).click();
  await page.getByRole('button', { name: '칠불경 (七佛經) 상세 보기' }).click();
  await page.getByRole('button', { name: '이 문헌에 대해 질문하기' }).click();
});