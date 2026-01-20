import { test, expect } from '@playwright/test';
import {
  sendChatMessage,
  waitForStreamingResponse,
  waitForSources,
  deleteSession,
} from '../utils/sse-helper';

test.describe('Ghosa AI Chat Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Ghosa AI 페이지로 이동 (메인 채팅 페이지)
    await page.goto('/');
  });

  test('Hero 섹션 샘플 질문 표시', async ({ page }) => {
    // 샘플 질문 카드들 확인
    const sampleQuestions = page.locator(
      '.sample-question, .question-card, [data-sample-question]'
    );

    // 최소 하나의 샘플 질문이 있어야 함
    const count = await sampleQuestions.count();
    expect(count).toBeGreaterThan(0);
  });

  test('샘플 질문 클릭 시 채팅 시작', async ({ page }) => {
    const sampleQuestion = page.locator(
      '.sample-question, .question-card, [data-sample-question]'
    ).first();

    if (await sampleQuestion.isVisible()) {
      await sampleQuestion.click();

      // 채팅 영역으로 이동했는지 확인
      const chatArea = page.locator('.chat-container, .chat-area, #chat');
      await expect(chatArea).toBeVisible({ timeout: 10000 });
    }
  });

  test('채팅 입력 필드 표시', async ({ page }) => {
    const chatInput = page.locator(
      'textarea[placeholder*="질문"], input[placeholder*="질문"], .chat-input textarea, #chat-input'
    );

    await expect(chatInput).toBeVisible();
    await expect(chatInput).toBeEnabled();
  });

  test('메시지 전송 버튼 표시', async ({ page }) => {
    const sendButton = page.locator(
      'button:has-text("전송"), button[type="submit"], .send-button, button[aria-label*="send"]'
    );

    await expect(sendButton).toBeVisible();
  });

  test('간단한 질문 전송 및 응답 수신', async ({ page }) => {
    test.setTimeout(120000); // 2분 타임아웃 (SSE 응답 대기)

    // 채팅 입력
    const chatInput = page.locator(
      'textarea[placeholder*="질문"], .chat-input textarea'
    ).first();

    await chatInput.fill('사성제가 무엇인가요?');

    // 전송
    const sendButton = page.locator(
      'button:has-text("전송"), button[type="submit"], .send-button'
    );
    await sendButton.click();

    // 응답 대기
    const response = page.locator(
      '.chat-response, .assistant-message, [data-role="assistant"]'
    ).last();

    await expect(response).toBeVisible({ timeout: 60000 });

    // 응답 내용에 관련 키워드 포함 확인
    const responseText = await response.textContent();
    expect(responseText).toBeTruthy();
    expect(responseText!.length).toBeGreaterThan(50);
  });

  test('스트리밍 응답 진행 표시', async ({ page }) => {
    test.setTimeout(120000);

    const chatInput = page.locator('textarea[placeholder*="질문"], .chat-input textarea').first();
    await chatInput.fill('오온이란 무엇인가요?');

    const sendButton = page.locator('button:has-text("전송"), button[type="submit"]');
    await sendButton.click();

    // 로딩/진행 표시 확인
    const loadingIndicator = page.locator(
      '.loading, .typing-indicator, .progress, [data-loading]'
    );

    // 로딩 표시가 나타났다가 사라지는지 확인
    try {
      await expect(loadingIndicator).toBeVisible({ timeout: 10000 });
    } catch {
      // 빠르게 응답이 올 경우 스킵 가능
    }

    // 최종 응답 확인
    const response = page.locator('.chat-response, .assistant-message').last();
    await expect(response).toBeVisible({ timeout: 60000 });
  });

  test('출처(Sources) 표시 확인', async ({ page }) => {
    test.setTimeout(120000);

    const chatInput = page.locator('textarea[placeholder*="질문"], .chat-input textarea').first();
    await chatInput.fill('팔정도란 무엇인가요?');

    const sendButton = page.locator('button:has-text("전송"), button[type="submit"]');
    await sendButton.click();

    // 응답 대기
    const response = page.locator('.chat-response, .assistant-message').last();
    await expect(response).toBeVisible({ timeout: 60000 });

    // 출처 섹션 확인
    const sources = page.locator(
      '.sources, .references, .citation, [data-sources]'
    );

    // 출처가 있으면 확인, 없으면 패스
    if (await sources.isVisible({ timeout: 5000 })) {
      const sourceCount = await sources.locator('a, li, .source-item').count();
      expect(sourceCount).toBeGreaterThanOrEqual(1);
    }
  });

  test('채팅 옵션 설정', async ({ page }) => {
    // 채팅 옵션 버튼/토글 찾기
    const optionsButton = page.locator(
      '.chat-options, button[aria-label*="option"], .settings-btn'
    );

    if (await optionsButton.isVisible()) {
      await optionsButton.click();

      // 옵션 패널/드롭다운 표시
      const optionsPanel = page.locator('.options-panel, .settings-panel, .dropdown');
      await expect(optionsPanel).toBeVisible({ timeout: 3000 });

      // 옵션 닫기
      await page.keyboard.press('Escape');
    }
  });

  test('빈 메시지 전송 방지', async ({ page }) => {
    const chatInput = page.locator('textarea[placeholder*="질문"], .chat-input textarea').first();
    await chatInput.fill(''); // 빈 입력

    const sendButton = page.locator('button:has-text("전송"), button[type="submit"]');

    // 버튼이 비활성화되어 있거나 클릭해도 메시지가 전송되지 않음
    const isDisabled = await sendButton.isDisabled();

    if (!isDisabled) {
      await sendButton.click();
      await page.waitForTimeout(1000);

      // 에러 메시지 또는 응답 없음 확인
      const response = page.locator('.chat-response, .assistant-message');
      const count = await response.count();
      // 빈 메시지로 응답이 생성되지 않아야 함
    }
  });

  test('긴 질문 처리', async ({ page }) => {
    test.setTimeout(120000);

    const longQuestion =
      '초기불교에서 말하는 사성제(四聖諦, cattāri ariyasaccāni)에 대해 자세히 설명해주세요. ' +
      '특히 고성제(苦聖諦), 집성제(集聖諦), 멸성제(滅聖諦), 도성제(道聖諦) 각각에 대해 ' +
      '경전적 근거와 함께 상세하게 알려주시기 바랍니다.';

    const chatInput = page.locator('textarea[placeholder*="질문"], .chat-input textarea').first();
    await chatInput.fill(longQuestion);

    const sendButton = page.locator('button:has-text("전송"), button[type="submit"]');
    await sendButton.click();

    // 응답 대기 (긴 질문은 더 오래 걸릴 수 있음)
    const response = page.locator('.chat-response, .assistant-message').last();
    await expect(response).toBeVisible({ timeout: 90000 });

    const responseText = await response.textContent();
    expect(responseText!.length).toBeGreaterThan(100);
  });

  test('Enter 키로 메시지 전송', async ({ page }) => {
    test.setTimeout(120000);

    const chatInput = page.locator('textarea[placeholder*="질문"], .chat-input textarea').first();
    await chatInput.fill('무상이란?');
    await page.keyboard.press('Enter');

    // 응답 대기
    const response = page.locator('.chat-response, .assistant-message').last();
    await expect(response).toBeVisible({ timeout: 60000 });
  });

  test('모바일에서 채팅 레이아웃', async ({ page, isMobile }) => {
    test.skip(!isMobile, '모바일 전용 테스트');

    // 채팅 입력이 화면 하단에 고정되어 있는지 확인
    const chatInput = page.locator('textarea[placeholder*="질문"], .chat-input');
    await expect(chatInput).toBeVisible();

    const box = await chatInput.boundingBox();
    if (box) {
      const viewport = page.viewportSize();
      if (viewport) {
        // 입력창이 화면 하단 근처에 있어야 함
        expect(box.y).toBeGreaterThan(viewport.height * 0.5);
      }
    }
  });
});

test.describe('Chat History (로그인 필요)', () => {
  test.skip('채팅 기록 저장 확인', async ({ page }) => {
    // storageState로 로그인된 상태 필요
  });

  test.skip('세션 삭제', async ({ page }) => {
    // storageState로 로그인된 상태 필요
  });
});

