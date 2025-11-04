# Feedback Management Guide

## 피드백 수집 방법

Buddha Korea 웹사이트의 피드백은 사용자 브라우저의 localStorage에 저장됩니다.

## 피드백 데이터 추출 방법

### 방법 1: 브라우저 콘솔 사용

1. Buddha Korea 웹사이트 열기
2. 개발자 도구 열기 (F12 또는 Ctrl+Shift+I)
3. Console 탭으로 이동
4. 다음 명령어 입력:

```javascript
exportAllFeedback()
```

5. 자동으로 JSON 파일이 다운로드됩니다

### 방법 2: localStorage 직접 확인

1. 개발자 도구 > Application 탭
2. Storage > Local Storage > 해당 도메인 선택
3. `buddhakoreafeedback` 키 찾기
4. 값을 복사하여 JSON 파일로 저장

## 피드백 데이터 구조

각 피드백은 다음 정보를 포함합니다:

```json
{
  "timestamp": "2024-11-03T12:00:00.000Z",
  "name": "이름 또는 익명",
  "email": "이메일 주소 (선택사항)",
  "phone": "전화번호 (선택사항)",
  "message": "사용자 메시지",
  "userAgent": "브라우저 정보",
  "language": "사용 언어"
}
```

## 데이터 관리 팁

- 정기적으로 피드백을 내보내고 백업하세요
- 민감한 개인정보는 별도로 안전하게 관리하세요
- 피드백 분석 후 실행 가능한 개선사항을 정리하세요

## localStorage 초기화

모든 피드백을 삭제하려면:

```javascript
localStorage.removeItem('buddhakoreafeedback')
```

## 주의사항

- localStorage는 브라우저별로 저장됩니다
- 사용자가 브라우저 데이터를 삭제하면 피드백도 삭제됩니다
- 중요한 피드백은 즉시 내보내기를 권장합니다