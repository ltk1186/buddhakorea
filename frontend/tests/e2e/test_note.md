아래 표는 BuddhaKorea(기업 서비스 가정) 기준으로 QA팀이 Playwright로 운영하기 좋은 “정석” 테스트 케이스 매트릭스입니다.
핵심은 우선순위(P0/P1/P2) × 실행 주기(Smoke/Regression/Nightly) × Mock/Real 전략을 명확히 분리해, 비용·플래키·유지보수를 통제하는 것입니다.

⸻

운영 전제(표 해석 기준)
• Auth: 테스트 전용 로그인(예: POST /auth/test-login)로 세션/JWT를 실제로 발급받아 사용
• Chat: 기본은 Deterministic(Mock/Cached) 모드로 실행(비용 0, 결과 결정적)
• Real LLM/RAG: Nightly(또는 pre-release) 에서만 소수 케이스로 “건강검진(healthcheck)” 수행
• 문장 일치 검증 금지, 구조/정상성만 검증
• 실행 주기 정의
• PR/Smoke: PR마다(또는 main merge마다) 3~5분 목표
• Regression: main merge 후 또는 하루 12회(1020분 목표)
• Nightly Real: 하루 1회(비용/시간 감안)

⸻

테스트 케이스 표 (우선순위/실행 주기/Mock vs Real)

표의 “Mode”에서
Mock = 네트워크 라우팅으로 응답을 가짜로 반환(프론트 UX 검증용)
Deterministic = 백엔드 TEST_MODE로 캐시된/고정된 답변 반환(파이프라인 통합 검증용)
Real = 실제 LLM/RAG 호출(최소만)

A. 인증/권한/세션 (AuthN/AuthZ)

ID 영역 케이스(요구사항) 우선순위 실행 주기 Mode 핵심 검증 포인트(Assertion) 비고/데이터
A-01 AuthZ 비로그인 상태에서 /chat 직접 접근 시 로그인 유도(redirect) P0 Smoke Real URL이 /login(또는 로그인 모달)로 전환, 보호 콘텐츠 미노출 라우팅 정책 확정 필요
A-02 AuthZ 비로그인 상태에서 /mypage 접근 차단 P0 Smoke Real redirect/모달 + 마이페이지 데이터 미노출
A-03 AuthN 테스트 로그인 후 /chat 정상 진입 P0 Smoke Real Chat UI 핵심 요소 렌더(입력창, 전송버튼) test-login 필수
A-04 AuthN 로그아웃 후 보호 페이지 재접근 차단 P0 Regression Real logout 후 /chat 접근 시 차단
A-05 AuthZ 로그아웃 후 뒤로가기(back)로 보호 페이지 노출 금지 P0 Regression Real back 후에도 보호 UI 미노출(redirect 유지) 캐시/히스토리 이슈 탐지
A-06 Session 세션/토큰 만료 시 재인증 유도 UX P1 Regression Real 강제 만료(쿠키 삭제/토큰 만료) 후 요청 시 안내/redirect 만료 재현 방법 합의
A-07 Profile 마이페이지 기본 정보 표시(이메일/닉네임 등) P1 Regression Real 표시 항목 존재 + 값 형식(비어있지 않음) 테스트 유저 고정

⸻

B. 쿼터/레이트리밋(비로그인 3회, 로그인 20회)

ID 영역 케이스(요구사항) 우선순위 실행 주기 Mode 핵심 검증 포인트(Assertion) 비고/데이터
B-01 Quota 비로그인 1~3회 질문 성공 P0 Regression Deterministic 1~3회 모두 응답 렌더 + 카운트 표시(있다면) 비용 0
B-02 Quota 비로그인 4회차 차단 + 안내 UX P0 Regression Deterministic 4회차에 paywall/로그인 유도/에러 코드 처리 UX 경계값 핵심
B-03 Quota 로그인 1~20회 질문 성공 P0 Regression Deterministic 1~20회 응답 렌더, 20회 도달 시 안내(있다면) 실행 시간 고려(루프/빠른 응답)
B-04 Quota 로그인 21회차 차단 + 안내 UX P0 Regression Deterministic 21회차 차단 UX/메시지 정확 경계값 핵심
B-05 Abuse 연타/중복 전송 방지(로딩 중 Send 여러 번) P1 Regression Mock 요청 1회만 발생(네트워크 카운트) + UI 잠금 route로 요청 수 체크
B-06 Reset 쿼터 리셋 시점(일일 초기화) 정책 검증 P2 Nightly/주기적 Deterministic 날짜 변경/리셋 후 카운트 초기화 시간 조작 전략 필요

⸻

C. 챗봇 UI/UX(기본 기능) — 비용 0로 상시 회귀

ID 영역 케이스(요구사항) 우선순위 실행 주기 Mode 핵심 검증 포인트(Assertion) 비고/데이터
C-01 Chat UI 채팅 페이지 로드(핵심 컴포넌트 렌더) P0 Smoke Real 입력창/전송버튼/메시지영역 존재 A-03과 묶어도 됨
C-02 Chat UX 메시지 입력 후 전송 시 사용자 버블 즉시 표시 P0 Smoke Mock 내 메시지 렌더(optimistic UI) LLM 불필요
C-03 Chat UX 로딩/스트리밍 인디케이터 표시 P1 Regression Mock 전송 후 spinner/typing 표시 스트리밍 UI가 있다면
C-04 Render 응답 메시지 렌더(줄바꿈/마크다운 최소) P1 Regression Mock 지정된 mock 응답이 UI에서 정상 표시 마크다운 정책 합의
C-05 Error UX 서버 500 시 오류 배너/재시도 UX P0 Regression Mock 500 응답 → 오류 표시, 재시도 동작 route.fulfill(500)
C-06 Timeout 응답 지연(예: 90초) 시 UX(대기/취소/안내) P1 Regression Mock 지연 시에도 UI가 멈추지 않고 안내 “취소” 기능 있으면 포함
C-07 Validation 빈 입력/공백 입력 전송 방지 P1 Regression Real send 비활성 또는 경고 메시지
C-08 Limits 너무 긴 입력 처리(프론트 제한/서버 오류 처리) P1 Regression Mock/Real 제한 메시지, 요청 차단 또는 4xx 처리 정책 필요
C-09 Copy 답변 복사(버튼 있다면) 기능 P2 Regression Mock clipboard 동작/토스트 표시 옵션

⸻

D. 히스토리/대화 상태(저장/조회/분리) — 신뢰/재방문 핵심

ID 영역 케이스(요구사항) 우선순위 실행 주기 Mode 핵심 검증 포인트(Assertion) 비고/데이터
D-01 History 질문/답변 저장 후 새로고침해도 유지 P0 Regression Deterministic refresh 후 동일 대화가 존재 비용 0, 통합 검증
D-02 History 대화 목록에서 특정 대화 선택 시 정확히 로드 P1 Regression Deterministic 선택한 대화의 메시지 set 표시
D-03 History 대화 삭제/아카이브(있다면) 동작 P1 Regression Deterministic 삭제 후 목록/상세 반영 기능 있을 때만
D-04 Isolation 사용자 A/B 분리: A의 히스토리가 B에 노출되지 않음 P0 Regression Deterministic 계정 전환 후 데이터 분리 검증 테스트 유저 2개 필요
D-05 Pagination 히스토리 페이지네이션/무한스크롤(있다면) P2 Regression Mock 추가 로드 정상 기능 있을 때만

⸻

E. 외부 링크/기본 페이지(NotebookLM/사경 등)

ID 영역 케이스(요구사항) 우선순위 실행 주기 Mode 핵심 검증 포인트(Assertion) 비고/데이터
E-01 Link NotebookLM 링크 클릭 시 정확한 URL/새탭 이동 P1 Smoke Real page.waitForEvent('popup') 후 URL 검증 외부서비스 가용성은 검증 X
E-02 Page 사경 페이지 진입 및 핵심 요소 렌더 P1 Smoke Real 주요 입력/버튼/뷰가 보임 “핵심 행동” 1개 정의 권장
E-03 Page 사경 핵심 행동 1개(저장/다음/완료 등) 정상 P1 Regression Real 행동 수행 후 성공 토스트/상태 변화
E-04 Nav 주요 네비게이션(홈↔챗↔사경↔마이페이지) 기본 동작 P2 Regression Real 각 페이지 진입 성공

⸻

F. 실 LLM/RAG 헬스체크(비용 발생) — 최소만

ID 영역 케이스(요구사항) 우선순위 실행 주기 Mode 핵심 검증 포인트(Assertion) 비용/안정성
F-01 Real RAG 실제 질문 1건 → 응답 비어있지 않음, 에러 없음 P1 Nightly Real 응답 길이> N, 오류 텍스트 없음 문장 일치 금지
F-02 Real RAG 출처가 나와야 하는 질문 → sources UI/구조 확인 P1 Nightly Real sources 영역 존재(또는 API 구조) RAG 파이프라인 건강검진
F-03 Real RAG 타임아웃/지연 시 UX 정상(120s) P2 Nightly Real 대기/안내 UX, 실패 시 재시도 비용/시간 주의

⸻

권장 실행 정책(운영 표준)

1. 태그/스위트 분리
   • @smoke : PR마다 필수 (A-01, A-03, C-02, E-01 정도의 최소)
   • @regression : main merge 후/하루 1회 (P0/P1 중심)
   • @real : nightly만 (F-01~F-03)

2. Mock vs Deterministic vs Real 사용 규칙
   • UX/에러/로딩: Mock가 최적 (빠르고 명확)
   • 저장/히스토리/권한 분리: Deterministic가 최적 (통합 경로 유지)
   • LLM 품질 자체: Playwright로 하지 말고, 별도 평가(RAGAS/오프라인 평가)로 분리
   • 실 LLM: “연결성 건강검진”만, 소수 케이스

3. 타임아웃 정책
   • 전역 30s
   • 채팅 응답 assertion만 120s 등으로 국소 확대

⸻

다음 단계(바로 실행 가능한 산출물)

원하시면 위 표를 기반으로: 1. Playwright 프로젝트 구조(폴더/파일/태그) 2. Test Auth Mode + Deterministic Chat Mode API 스펙 3. 위 표의 P0 Smoke/Regression 케이스를 실제 Playwright 코드 템플릿으로 제공
까지 한 번에 정리해드릴 수 있습니다.

원활히 코드까지 내려가려면, 두 가지만 알려주시면 됩니다:
• 인증이 세션 쿠키인지 **JWT(Bearer)**인지
• chat API endpoint 경로(예: /api/chat) 및 히스토리 endpoint 유무
