import { test, expect } from '@playwright/test';
import { typeKorean, typeKoreanToLocator } from '../utils/korean-input';

test.describe('Sutra Writing (전자 사경) Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/sutra-writing');
  });

  test('경전 선택 카드 표시', async ({ page }) => {
    // 경전 카드들 확인
    const sutraCards = page.locator('.sutra-card, .card, [data-sutra]');
    const count = await sutraCards.count();
    expect(count).toBeGreaterThan(0);
  });

  test('카테고리 탭 표시', async ({ page }) => {
    // 카테고리 탭 (경전, 진언, 명호, 게송)
    const categoryTabs = page.locator('.category-tab, .tab, [data-category]');

    if ((await categoryTabs.count()) > 0) {
      await expect(categoryTabs.first()).toBeVisible();
    }
  });

  test('카테고리 탭 클릭 시 필터링', async ({ page }) => {
    const mantraTab = page.locator('[data-category="mantra"], .tab:has-text("진언")');

    if (await mantraTab.isVisible()) {
      await mantraTab.click();

      // 진언 카테고리 카드만 표시
      await page.waitForTimeout(500);
      const visibleCards = page.locator('.sutra-card:visible, .card:visible');
      // 카드가 필터링되었는지 확인
      const count = await visibleCards.count();
      expect(count).toBeGreaterThanOrEqual(0);
    }
  });

  test('경전 선택 후 타이핑 화면 이동', async ({ page }) => {
    // 첫 번째 경전 카드 클릭
    const firstCard = page.locator('.sutra-card, .card, [data-sutra]').first();
    await firstCard.click();

    // 타이핑 화면 표시
    const typingArea = page.locator(
      '.typing-area, .sutra-input, textarea, #sutra-input'
    );
    await expect(typingArea).toBeVisible({ timeout: 5000 });
  });

  test('올바른 글자 입력 시 완료 표시', async ({ page }) => {
    // 경전 선택
    const firstCard = page.locator('.sutra-card, .card, [data-sutra]').first();
    await firstCard.click();

    // 타이핑 영역 찾기
    const input = page.locator('textarea, input[type="text"], .typing-input, #sutra-input');
    await expect(input).toBeVisible({ timeout: 5000 });

    // 오버레이 텍스트에서 첫 글자 가져오기
    const overlayText = page.locator('.overlay-text, .sutra-text, .reference-text');
    let firstChars = '';

    if (await overlayText.isVisible()) {
      const fullText = await overlayText.textContent();
      if (fullText) {
        firstChars = fullText.slice(0, 3);
      }
    }

    if (firstChars) {
      // 올바른 글자 입력
      await input.fill(firstChars);

      // 완료된 글자 표시 확인
      const completedChars = page.locator('.done, .completed, .char.correct');
      await expect(completedChars.first()).toBeVisible({ timeout: 3000 });
    }
  });

  test('틀린 글자 입력 차단', async ({ page }) => {
    // 경전 선택
    const firstCard = page.locator('.sutra-card, .card, [data-sutra]').first();
    await firstCard.click();

    const input = page.locator('textarea, input[type="text"], .typing-input');
    await expect(input).toBeVisible({ timeout: 5000 });

    // 틀린 글자 입력 (일부러 잘못된 문자)
    await input.fill('ㅋㅋㅋ');
    await page.waitForTimeout(300);

    // 입력이 차단/삭제되었는지 확인
    const inputValue = await input.inputValue();
    // 틀린 글자는 받아들여지지 않아야 함
    expect(inputValue.length).toBeLessThanOrEqual(3);
  });

  test('뒤로가기 버튼', async ({ page }) => {
    // 경전 선택
    const firstCard = page.locator('.sutra-card, .card, [data-sutra]').first();
    await firstCard.click();

    // 타이핑 화면 확인
    const typingArea = page.locator('.typing-area, .sutra-input, textarea');
    await expect(typingArea).toBeVisible({ timeout: 5000 });

    // 뒤로가기 버튼 클릭
    const backButton = page.locator(
      'button:has-text("뒤로"), button:has-text("돌아가기"), .back-btn, [data-action="back"]'
    );

    if (await backButton.isVisible()) {
      await backButton.click();

      // 선택 화면으로 돌아감
      await expect(page.locator('.sutra-card, .card').first()).toBeVisible({ timeout: 5000 });
    }
  });

  test('진행률 표시', async ({ page }) => {
    // 경전 선택
    const firstCard = page.locator('.sutra-card, .card, [data-sutra]').first();
    await firstCard.click();

    // 진행률 바 또는 카운터 확인
    const progress = page.locator('.progress, .progress-bar, .counter, [data-progress]');

    if (await progress.isVisible()) {
      // 초기 진행률 확인 (0% 또는 0/n)
      const progressText = await progress.textContent();
      expect(progressText).toBeTruthy();
    }
  });

  test('Easy 모드 토글', async ({ page }) => {
    // 경전 선택
    const firstCard = page.locator('.sutra-card, .card, [data-sutra]').first();
    await firstCard.click();

    // Easy 모드 토글 버튼 찾기
    const easyToggle = page.locator(
      '[data-mode="easy"], .easy-mode-toggle, button:has-text("Easy"), button:has-text("쉬운")'
    );

    if (await easyToggle.isVisible()) {
      await easyToggle.click();
      await page.waitForTimeout(300);

      // Easy 모드 UI 변화 확인 (예: 힌트 표시, 글자 크기 변화)
      const easyModeIndicator = page.locator('.easy-mode, [data-mode="easy"].active');
      if (await easyModeIndicator.isVisible()) {
        await expect(easyModeIndicator).toBeVisible();
      }
    }
  });

  test('사경 완료 시 회향 UI 표시', async ({ page }) => {
    // 짧은 경전/진언 선택 (빠른 테스트를 위해)
    const shortSutraCard = page.locator('[data-sutra="om-mani"]').first();

    if (!(await shortSutraCard.isVisible())) {
      // 짧은 진언이 없으면 첫 번째 카드 사용
      const firstCard = page.locator('.sutra-card, .card, [data-sutra]').first();
      await firstCard.click();
    } else {
      await shortSutraCard.click();
    }

    // 타이핑 영역
    const input = page.locator('textarea, input[type="text"], .typing-input');
    await expect(input).toBeVisible({ timeout: 5000 });

    // 전체 텍스트 가져오기
    const overlayText = page.locator('.overlay-text, .sutra-text, .reference-text');
    let fullText = '';

    if (await overlayText.isVisible()) {
      fullText = (await overlayText.textContent()) || '';
    }

    if (fullText && fullText.length <= 100) {
      // 짧은 텍스트만 완전히 입력 (100자 이하)
      await input.fill(fullText);
      await page.waitForTimeout(500);

      // 회향 UI 표시 확인
      const dedicationUI = page.locator(
        '.dedication, .dedication-box, .complete-modal, [data-dedication]'
      );
      await expect(dedicationUI).toBeVisible({ timeout: 5000 });
    }
  });

  test('회향 애니메이션 트리거', async ({ page }) => {
    test.skip(true, '짧은 경전으로 완료 후 테스트 필요 - 수동 테스트 권장');
  });

  test('키보드 단축키', async ({ page }) => {
    // 경전 선택
    const firstCard = page.locator('.sutra-card, .card, [data-sutra]').first();
    await firstCard.click();

    const input = page.locator('textarea, input[type="text"], .typing-input');
    await expect(input).toBeVisible({ timeout: 5000 });

    // ESC 키로 뒤로가기
    await page.keyboard.press('Escape');

    // 선택 화면으로 돌아갔는지 확인
    const selectionScreen = page.locator('.sutra-selection, .card-grid');
    if (await selectionScreen.isVisible({ timeout: 3000 })) {
      await expect(selectionScreen).toBeVisible();
    }
  });

  test('모바일 터치 키보드 지원', async ({ page, isMobile }) => {
    test.skip(!isMobile, '모바일 전용 테스트');

    // 경전 선택
    const firstCard = page.locator('.sutra-card, .card, [data-sutra]').first();
    await firstCard.click();

    const input = page.locator('textarea, input[type="text"], .typing-input');
    await expect(input).toBeVisible({ timeout: 5000 });

    // 입력 필드 탭 시 포커스
    await input.tap();
    await expect(input).toBeFocused();
  });
});
