# Buddha Korea Playwright E2E 테스트 설정 계획

> 작성일: 2025-01-07

## 개요

| 항목 | 내용 |
|------|------|
| 언어 | TypeScript |
| MCP | 함께 설정 (Microsoft 공식) |
| 테스트 범위 | 전체 기능 |
| API 테스트 | 실제 API 사용 (https://ai.buddhakorea.com) |
| 인증 테스트 | 테스트 계정 사용 (storageState 활용) |

---

## 1. 디렉토리 구조

```
buddhakorea/frontend/
├── package.json                 # 새로 생성
├── playwright.config.ts         # Playwright 설정
├── tsconfig.json               # TypeScript 설정
├── tests/
│   ├── e2e/
│   │   ├── navigation.spec.ts       # 전체 네비게이션
│   │   ├── auth.spec.ts             # 로그인/인증
│   │   ├── ghosa-ai.spec.ts         # Ghosa AI 채팅
│   │   ├── mypage.spec.ts           # 마이페이지
│   │   ├── ephemeral.spec.ts        # 찰나의 문장
│   │   ├── sutra-writing.spec.ts    # 전자 사경
│   │   ├── meditation.spec.ts       # 명상 타이머
│   │   ├── teaching.spec.ts         # 교학 페이지
│   │   └── library.spec.ts          # 문헌 라이브러리
│   ├── fixtures/
│   │   └── page-objects/
│   │       ├── ChatPage.ts          # Ghosa AI 페이지
│   │       ├── SutraPage.ts
│   │       ├── MeditationPage.ts
│   │       └── TeachingPage.ts
│   └── utils/
│       ├── korean-input.ts          # 한글 IME 유틸리티
│       ├── auth-helper.ts           # 인증 헬퍼
│       └── sse-helper.ts            # SSE 테스트 헬퍼
├── .github/workflows/
│   └── playwright.yml               # CI/CD
└── mcp-config/
    └── playwright-mcp.json
```

---

## 2. 구현 단계

### Step 1: 초기 설정
```bash
cd /Users/vairocana/Desktop/buddhakorea/buddhakorea/frontend
npm init -y
npm install -D @playwright/test typescript @types/node serve
npx playwright install
```

### Step 2: package.json 스크립트
```json
{
  "scripts": {
    "test": "playwright test",
    "test:ui": "playwright test --ui",
    "test:headed": "playwright test --headed",
    "test:debug": "playwright test --debug",
    "test:report": "playwright show-report",
    "serve": "npx serve . -l 3000"
  }
}
```

### Step 3: playwright.config.ts 작성

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,

  reporter: [
    ['html', { open: 'never' }],
    ['list'],
  ],

  use: {
    baseURL: 'http://localhost:3000',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
    locale: 'ko-KR',
    timezoneId: 'Asia/Seoul',
  },

  webServer: {
    command: 'npx serve . -l 3000',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },

  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'mobile', use: { ...devices['iPhone 13'] } },
  ],
});
```

### Step 4: 테스트 파일 작성 (우선순위 순)
1. navigation.spec.ts - 전체 네비게이션
2. auth.spec.ts - 로그인/인증 (Google, Naver, 카카오)
3. ghosa-ai.spec.ts - Ghosa AI 채팅 (SSE 스트리밍)
4. sutra-writing.spec.ts - 전자 사경
5. ephemeral.spec.ts - 찰나의 문장
6. meditation.spec.ts - 명상 타이머
7. teaching.spec.ts - 교학 페이지
8. library.spec.ts - 문헌 라이브러리
9. mypage.spec.ts - 마이페이지

### Step 5: MCP 설정 (Microsoft 공식 Playwright MCP)

```json
// Claude Desktop: ~/Library/Application Support/Claude/claude_desktop_config.json
// Claude Code: ~/.claude/settings.json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

- GitHub: https://github.com/microsoft/playwright-mcp
- 스냅샷 기반 (스크린샷 불필요, 빠름)
- accessibility tree 사용으로 LLM 친화적

### Step 6: GitHub Actions CI/CD

```yaml
# .github/workflows/playwright.yml
name: Playwright Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - name: Install dependencies
        working-directory: buddhakorea/frontend
        run: npm ci
      - name: Install Playwright
        run: npx playwright install --with-deps
      - name: Run tests
        run: npm test
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report
          path: playwright-report/
```

---

## 3. 핵심 테스트 케이스

### 로그인/인증 (auth.spec.ts)
- 로그인 모달 열기/닫기
- Google 로그인 버튼 → OAuth 리다이렉트 확인
- Naver 로그인 버튼 → OAuth 리다이렉트 확인
- 카카오 로그인 버튼 → OAuth 리다이렉트 확인
- 로그인 상태 → 헤더에 "사용자명님" 표시
- 로그아웃 → 로그인 버튼으로 변경
- 비로그인 시 마이페이지 접근 → 로그인 프롬프트

### Ghosa AI 채팅 (ghosa-ai.spec.ts)
- Hero 섹션 샘플 질문 클릭 → 채팅 시작
- 메시지 입력 → 전송
- SSE 스트리밍 응답 수신 확인
- 진행 상태 표시 (문헌 검색 → 분석 → 답변 작성)
- 출처(sources) 표시 확인
- 채팅 옵션 변경 (응답 모드, 전통 필터)
- 문헌 제한 검색 (selectedSutra)
- 채팅 기록 저장 (로그인 사용자)
- 세션 삭제
- 쿼터 초과 시 에러 처리

### 마이페이지 (mypage.spec.ts)
- 프로필 정보 표시 (닉네임, 이메일, 가입일)
- 오늘의 사용량 표시
- 연결된 계정 표시 (Google, Naver, 카카오)
- 로그아웃 버튼 동작

### 찰나의 문장 (ephemeral.spec.ts)
- 모달 열기/닫기
- 한글 타이핑 → char-wrapper 래핑 확인
- FADE_DELAY(1.5초) 후 페이드 시작
- 애니메이션 완료 후 캔버스 초기화

### 전자 사경 (sutra-writing.spec.ts)
- 카테고리 탭 동작
- 올바른 글자 → `.done` 클래스
- 틀린 글자 → 자동 삭제
- 전체 완성 → 회향 박스 표시
- 회향 애니메이션 (char-ascending)
- Traditional/Easy 모드 전환

### 명상 타이머 (meditation.spec.ts)
- 탭 전환 (호흡/관상)
- 시간 카드 선택
- 타이머 시작/중단
- 완료 시 종소리

### 교학 (teaching.spec.ts)
- 사성제/팔정도/37보리분법/12연기 다이어그램
- 카드 클릭 → 설명 패널
- 12연기 순관/역관 토글
- 자동 재생/속도 조절

### 문헌 라이브러리 (library.spec.ts)
- 검색 디바운싱
- 필터 드롭다운
- 무한 스크롤
- 모달 네비게이션

---

## 4. 한글 IME 처리

```typescript
// tests/utils/korean-input.ts
import { Page } from '@playwright/test';

export async function typeKorean(page: Page, selector: string, text: string) {
  const element = page.locator(selector);
  await element.focus();

  for (const char of text) {
    await page.dispatchEvent(selector, 'compositionstart', {});
    await page.dispatchEvent(selector, 'compositionupdate', { data: char });
    await element.press(char);
    await page.dispatchEvent(selector, 'compositionend', { data: char });
    await page.waitForTimeout(50);
  }
}
```

---

## 5. 생성할 파일 목록

| 파일 | 용도 |
|------|------|
| `frontend/package.json` | 새로 생성 |
| `frontend/playwright.config.ts` | 새로 생성 |
| `frontend/tsconfig.json` | 새로 생성 |
| `frontend/tests/e2e/*.spec.ts` | 테스트 파일들 (9개) |
| `frontend/tests/utils/korean-input.ts` | 한글 유틸리티 |
| `frontend/tests/utils/auth-helper.ts` | 인증 테스트 헬퍼 |
| `frontend/tests/utils/sse-helper.ts` | SSE 스트리밍 테스트 헬퍼 |
| `frontend/.github/workflows/playwright.yml` | CI/CD |

---

## 6. 기술적 고려사항

| 도전 과제 | 해결책 |
|----------|--------|
| 한글 입력 | typeKorean 유틸리티로 IME 시뮬레이션 |
| CSS 애니메이션 대기 | waitForSelector + waitForTimeout |
| JSON 데이터 로딩 | 데이터 로드 완료 대기 |
| Web Audio (종소리) | 함수 호출 여부만 확인 |
| contenteditable | type() 또는 커스텀 입력 함수 |
| **OAuth 로그인** | 테스트 계정으로 실제 로그인 → storageState 저장 |
| **SSE 스트리밍** | 실제 API 사용, 응답 완료까지 대기 |
| **쿠키 인증** | storageState로 로그인 상태 저장/복원 |
| **외부 API** | https://ai.buddhakorea.com 실제 사용 |

---

## 7. 실행 명령어

```bash
npm test                    # 전체 테스트
npm run test:ui             # UI 모드 (디버깅)
npm run test:headed         # 브라우저 표시
npx playwright test sutra   # 특정 테스트만
npm run test:report         # 리포트 확인
```

---

## 참고 자료

- [Playwright 공식 문서](https://playwright.dev/)
- [Microsoft Playwright MCP](https://github.com/microsoft/playwright-mcp)
- [Playwright MCP Guide 2025](https://medium.com/@bluudit/playwright-mcp-comprehensive-guide-to-ai-powered-browser-automation-in-2025-712c9fd6cffa)
