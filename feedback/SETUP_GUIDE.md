# 피드백 시스템 설정 가이드

## 🚀 실제 웹사이트에서 피드백 받는 방법

현재 피드백 시스템은 **EmailJS**를 통해 이메일로 피드백을 받을 수 있도록 준비되어 있습니다.

## 방법 1: EmailJS 설정 (추천) - 무료, 서버 불필요

### 1단계: EmailJS 계정 생성

1. [EmailJS](https://www.emailjs.com/) 사이트 방문
2. **Sign Up Free** 클릭 (무료 계정은 월 200개 이메일 가능)
3. 계정 생성 후 로그인

### 2단계: 이메일 서비스 연결

1. Dashboard에서 **Email Services** 탭 클릭
2. **Add New Service** 클릭
3. **Gmail** 선택 (가장 간단함)
4. Service Name 입력 (예: "BuddhaKorea")
5. **Connect Account** 클릭하여 Gmail 계정 연결
6. Service ID 복사 (예: `service_abc123`)

### 3단계: 이메일 템플릿 생성

1. **Email Templates** 탭 클릭
2. **Create New Template** 클릭
3. 템플릿 설정:

**Template Name**: Buddha Korea Feedback

**To Email**: 여러분의 이메일 주소

**From Name**: {{from_name}}

**Subject**: [Buddha Korea 피드백] {{from_name}}님의 의견

**Content**:
```
새로운 피드백이 도착했습니다!

이름: {{from_name}}
이메일: {{from_email}}
전화번호: {{phone}}
시간: {{timestamp}}

메시지:
{{message}}

---
브라우저 정보:
{{user_agent}}
```

4. **Save** 클릭
5. Template ID 복사 (예: `template_xyz789`)

### 4단계: Public Key 가져오기

1. **Account** 탭 클릭
2. **API Keys** 섹션에서 **Public Key** 복사

### 5단계: 웹사이트에 적용

`js/feedback.js` 파일을 열고 상단의 설정을 업데이트:

```javascript
const EMAILJS_CONFIG = {
    SERVICE_ID: 'service_abc123',    // 여기에 실제 Service ID
    TEMPLATE_ID: 'template_xyz789',  // 여기에 실제 Template ID
    PUBLIC_KEY: 'AbCdEfGhIjKlMnOp'   // 여기에 실제 Public Key
};
```

### 완료!

이제 사용자가 피드백을 제출하면 자동으로 이메일로 받게 됩니다.

---

## 방법 2: Google Forms 사용 (더 간단)

EmailJS 설정이 복잡하다면, Google Forms를 사용할 수 있습니다:

1. [Google Forms](https://forms.google.com) 에서 폼 생성
2. 필드 추가: 이름(선택), 이메일(선택), 전화번호(선택), 메시지(필수)
3. 설정에서 "응답을 이메일로 받기" 활성화
4. 폼 링크를 얻어서 피드백 버튼이 새 창에서 Google Form을 열도록 변경

`js/feedback.js`에서:
```javascript
function openFeedbackModal() {
    window.open('https://forms.google.com/YOUR_FORM_LINK', '_blank');
}
```

---

## 방법 3: Netlify Forms (Netlify 호스팅 시)

Netlify에서 호스팅한다면, Netlify Forms를 사용할 수 있습니다:

1. HTML form에 `netlify` 속성 추가:
```html
<form id="feedback-form" class="feedback-form" netlify>
```

2. Netlify 대시보드에서 폼 제출 확인 및 이메일 알림 설정

---

## 현재 로컬 저장소 방식

EmailJS를 설정하지 않으면, 피드백은 사용자의 브라우저 localStorage에만 저장됩니다.

### 로컬 피드백 확인 방법:

1. 웹사이트 열기
2. 개발자 도구 (F12) > Console
3. 다음 명령어 입력:
```javascript
exportAllFeedback()
```
4. JSON 파일로 다운로드됨

---

## 문제 해결

### EmailJS가 작동하지 않는 경우:

1. **Console 확인**: 브라우저 개발자 도구에서 오류 메시지 확인
2. **API 키 확인**: Service ID, Template ID, Public Key가 정확한지 확인
3. **이메일 한도**: 무료 계정은 월 200개 제한
4. **스팸 폴더**: 이메일이 스팸 폴더로 갈 수 있음

### 보안 참고사항:

- Public Key는 공개되어도 안전함 (이름 그대로 public)
- Private Key는 절대 클라이언트 코드에 넣지 마세요
- 민감한 정보는 HTTPS 사이트에서만 수집하세요

---

## 추천 설정

1. **기본**: EmailJS (무료, 간단, 서버 불필요)
2. **간편**: Google Forms (가장 쉬움, 커스터마이징 제한)
3. **전문**: 백엔드 서버 구축 (완전한 제어, 기술 필요)

질문이 있으시면 언제든 문의해주세요!