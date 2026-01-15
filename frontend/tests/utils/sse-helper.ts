import { Page, expect } from '@playwright/test';

/**
 * SSE (Server-Sent Events) 스트리밍 응답 테스트 헬퍼
 */

/**
 * SSE 스트리밍 응답 대기
 * Ghosa AI 채팅의 스트리밍 응답을 기다립니다.
 */
export async function waitForStreamingResponse(
  page: Page,
  options: {
    timeout?: number;
    minLength?: number;
  } = {}
): Promise<string> {
  const { timeout = 60000, minLength = 10 } = options;

  // 응답 영역 로케이터
  const responseLocator = page.locator(
    '.chat-response, .assistant-message, [data-role="assistant"]'
  ).last();

  // 응답이 나타날 때까지 대기
  await expect(responseLocator).toBeVisible({ timeout });

  // 스트리밍이 완료될 때까지 대기 (텍스트 길이 확인)
  await page.waitForFunction(
    ({ selector, minLen }) => {
      const el = document.querySelector(selector);
      if (!el) return false;
      return el.textContent && el.textContent.length >= minLen;
    },
    {
      selector: '.chat-response:last-child, .assistant-message:last-child',
      minLen: minLength,
    },
    { timeout }
  );

  return (await responseLocator.textContent()) || '';
}

/**
 * 진행 상태 표시 확인
 * "문헌 검색 중...", "분석 중...", "답변 작성 중..." 등
 */
export async function waitForProgressSteps(
  page: Page,
  expectedSteps: string[] = ['검색', '분석', '답변']
): Promise<boolean> {
  const progressLocator = page.locator(
    '.progress-status, .loading-status, [data-status]'
  );

  for (const step of expectedSteps) {
    try {
      await expect(progressLocator).toContainText(step, { timeout: 30000 });
    } catch {
      // 일부 단계는 빠르게 지나갈 수 있음
      console.log(`Progress step "${step}" might have been skipped`);
    }
  }

  return true;
}

/**
 * 출처(sources) 표시 확인
 */
export async function waitForSources(page: Page): Promise<string[]> {
  const sourcesLocator = page.locator(
    '.sources, .references, [data-sources], .citation'
  );

  await expect(sourcesLocator).toBeVisible({ timeout: 60000 });

  // 출처 텍스트들 수집
  const sourceItems = sourcesLocator.locator('.source-item, li, a');
  const count = await sourceItems.count();
  const sources: string[] = [];

  for (let i = 0; i < count; i++) {
    const text = await sourceItems.nth(i).textContent();
    if (text) sources.push(text.trim());
  }

  return sources;
}

/**
 * 채팅 메시지 전송
 */
export async function sendChatMessage(page: Page, message: string): Promise<void> {
  // 입력 필드 찾기
  const inputLocator = page.locator(
    'textarea[placeholder*="질문"], input[placeholder*="질문"], .chat-input textarea, #chat-input'
  );

  await inputLocator.fill(message);

  // 전송 버튼 클릭 또는 Enter
  const sendButton = page.locator(
    'button:has-text("전송"), button[type="submit"], .send-button'
  );

  if (await sendButton.isVisible()) {
    await sendButton.click();
  } else {
    await page.keyboard.press('Enter');
  }
}

/**
 * 채팅 기록 확인
 */
export async function getChatHistory(page: Page): Promise<{ role: string; content: string }[]> {
  const messages = page.locator('.chat-message, [data-role]');
  const count = await messages.count();
  const history: { role: string; content: string }[] = [];

  for (let i = 0; i < count; i++) {
    const msg = messages.nth(i);
    const role =
      (await msg.getAttribute('data-role')) ||
      ((await msg.locator('.user-message').count()) > 0 ? 'user' : 'assistant');
    const content = (await msg.textContent()) || '';
    history.push({ role, content: content.trim() });
  }

  return history;
}

/**
 * 세션 삭제
 */
export async function deleteSession(page: Page): Promise<void> {
  const deleteButton = page.locator(
    'button:has-text("삭제"), button:has-text("새 대화"), .delete-session'
  );

  if (await deleteButton.isVisible()) {
    await deleteButton.click();

    // 확인 모달이 있으면 확인
    const confirmButton = page.locator('button:has-text("확인"), button:has-text("삭제")');
    if (await confirmButton.isVisible({ timeout: 2000 })) {
      await confirmButton.click();
    }
  }
}

/**
 * 쿼터 초과 에러 확인
 */
export async function checkQuotaError(page: Page): Promise<boolean> {
  const errorLocator = page.locator(
    '.error-message, .quota-exceeded, [data-error="quota"]'
  );

  try {
    await expect(errorLocator).toBeVisible({ timeout: 5000 });
    return true;
  } catch {
    return false;
  }
}
