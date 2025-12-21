# Authentication & User Database Documentation

## Overview
The authentication system uses **OAuth 2.0** for social login (Google, Naver, Kakao) and **JWT (JSON Web Tokens)** for maintaining user sessions.

## Architecture

### 1. Database Schema (`users` table)
| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary Key |
| `email` | String | Unique email address |
| `provider` | String | OAuth provider (google, naver, kakao) |
| `social_id` | String | Unique ID from the provider |
| `nickname` | String | User's display name |
| `profile_img`| String | URL to profile image |
| `created_at` | DateTime | Account creation timestamp |
| `last_login` | DateTime | Last login timestamp |

### 2. Auth Flow
1. **Frontend**: User clicks "Login with Google".
2. **Backend**: Redirects to Google OAuth consent screen (`/auth/login/google`).
3. **Callback**: Google redirects back to `/auth/callback/google` with a code.
4. **Processing**:
   - Backend exchanges code for access token.
   - Fetches user info (email, profile).
   - Checks DB: Updates existing user or creates a new one.
   - Generates a **JWT** containing `user_id` and `email`.
5. **Session**: Backend sets a `HttpOnly`, `Secure` cookie named `access_token` containing the JWT.
6. **Frontend**: Receives control back. Calls `/api/users/me` to get user info.

## Configuration
Required environment variables in `.env`:
```env
SECRET_KEY=your-secure-random-key
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
# (Same for NAVER and KAKAO)
```

## API Endpoints
- `GET /auth/login/{provider}`: Start login flow.
- `GET /auth/callback/{provider}`: OAuth callback handler.
- `POST /auth/logout`: clear session cookie.
- `GET /api/users/me`: Get current user profile.

## Security
- **JWT**: Signed with HS256 algorithm.
- **Cookies**: `HttpOnly` prevents XSS attacks accessing the token. `Secure` ensures transmission only over HTTPS. `Domain` is configurable via `COOKIE_DOMAIN` env var (set to `.buddhakorea.com` in production, leave empty for localhost).

---

## TODO: Frontend Auth UI Implementation

### 1. File Structure
```
frontend/
├── js/
│   └── auth.js              ← 새로 생성 (인증 로직)
├── css/
│   └── auth.css             ← 새로 생성 (인증 UI 스타일)
├── index.html               ← auth.js 연동
├── chat.html                ← auth.js 연동 + 계정 탭 추가
└── sutra-writing.html       ← auth.js 연동
```

### 2. Page-Specific UI Placement

#### index.html & sutra-writing.html (헤더)
```
┌─────────────────────────────────────────────────────────┐
│ 🪷 Buddha Korea     홈   AI   사경         [Google 로그인] │ ← 비로그인
├─────────────────────────────────────────────────────────┤
│ 🪷 Buddha Korea     홈   AI   사경          🔵 김철수 ▼  │ ← 로그인 후
└─────────────────────────────────────────────────────────┘
```

#### chat.html (데스크톱 - 좌측 네비 하단)
```
┌──────────┬────────────────────────────────────┐
│ ☸ 불교AI │                                    │
│ ─────────│                                    │
│ 💬 채팅   │          채팅 영역                  │
│ 📚 라이브 │                                    │
│ 📖 방법론 │                                    │
│ ─────────│                                    │
│ 👤 계정  │  ← 하단에 계정 버튼 추가             │
└──────────┴────────────────────────────────────┘
```

#### chat.html (모바일 - 하단 탭 바)
```
┌────────────────────────────────┐
│          채팅 영역              │
├───────┬───────┬────────┬───────┤
│ 채팅  │라이브 │ 방법론  │ 계정  │
└───────┴───────┴────────┴───────┘
```

### 3. auth.js Module Design
```javascript
const Auth = {
    user: null,
    isLoggedIn: false,

    async init(config) {
        // config: { containerId, style: 'header' | 'sidebar' | 'tab' }
        await this.checkAuthStatus();
        this.render(config);
    },

    async checkAuthStatus() {
        const response = await fetch('/api/users/me', { credentials: 'include' });
        if (response.ok) {
            this.user = await response.json();
            this.isLoggedIn = true;
        }
    },

    render(config) { /* 페이지별 다른 스타일로 렌더링 */ },
    login(provider = 'google') { window.location.href = `/auth/login/${provider}`; },
    async logout() { /* POST /auth/logout → reload */ },
    toggleDropdown() { /* 프로필 드롭다운 */ }
};
```

### 4. User Flow

#### Login Flow
1. User clicks "로그인" or "계정" button
2. Dropdown shows: "Google로 로그인" (+ Naver/Kakao later)
3. OAuth redirect → callback → JWT cookie set → redirect back
4. Page loads → auth.js calls `/api/users/me`
5. UI updates to show profile image + nickname

#### Logout Flow
1. Click "로그아웃" in dropdown
2. `POST /auth/logout` → cookie cleared
3. UI updates to show login button

### 5. Implementation Phases

**Phase 1: 기본 인증 UI**
- [ ] auth.js 생성 (checkAuth, login, logout)
- [ ] auth.css 생성 (버튼, 드롭다운 스타일)
- [ ] index.html 연동 (기존 인라인 JS 제거)
- [ ] sutra-writing.html 연동

**Phase 2: chat.html 연동**
- [ ] chat.html 좌측 네비에 계정 영역 추가 (데스크톱)
- [ ] chat.html 탭 바에 계정 탭 추가 (모바일)
- [ ] 스타일 통일

**Phase 3: 드롭다운 & UX 개선**
- [ ] 프로필 드롭다운 구현
- [ ] 로그인 제공자 선택 드롭다운 (Google/Naver/Kakao)
- [ ] 로딩 상태, 에러 처리
