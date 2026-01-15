import { Page, Locator } from '@playwright/test';

/**
 * 한글 IME 입력 시뮬레이션
 *
 * Playwright는 기본적으로 한글 조합(composition)을 처리하지 않으므로,
 * compositionstart/compositionupdate/compositionend 이벤트를 수동으로 발생시킵니다.
 */
export async function typeKorean(page: Page, selector: string, text: string): Promise<void> {
  const element = page.locator(selector);
  await element.focus();

  for (const char of text) {
    // 조합 시작
    await page.dispatchEvent(selector, 'compositionstart', {});

    // 조합 중 (글자 입력)
    await page.dispatchEvent(selector, 'compositionupdate', { data: char });

    // 실제 키 입력
    await element.pressSequentially(char, { delay: 30 });

    // 조합 완료
    await page.dispatchEvent(selector, 'compositionend', { data: char });

    // 다음 글자 전 약간의 딜레이
    await page.waitForTimeout(50);
  }
}

/**
 * Locator를 사용한 한글 입력
 */
export async function typeKoreanToLocator(
  page: Page,
  locator: Locator,
  text: string
): Promise<void> {
  await locator.focus();

  for (const char of text) {
    await locator.dispatchEvent('compositionstart', {});
    await locator.dispatchEvent('compositionupdate', { data: char });
    await locator.pressSequentially(char, { delay: 30 });
    await locator.dispatchEvent('compositionend', { data: char });
    await page.waitForTimeout(50);
  }
}

/**
 * 빠른 한글 입력 (조합 이벤트 없이)
 * 일반 텍스트 입력에 사용
 */
export async function typeKoreanFast(locator: Locator, text: string): Promise<void> {
  await locator.fill(text);
}

/**
 * 한글 입력 후 엔터키
 */
export async function typeKoreanAndEnter(
  page: Page,
  selector: string,
  text: string
): Promise<void> {
  await typeKorean(page, selector, text);
  await page.keyboard.press('Enter');
}
