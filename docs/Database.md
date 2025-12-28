# Buddha Korea Database 스키마 문서

이 문서는 Buddha Korea 프로젝트의 PostgreSQL 데이터베이스 스키마와 개발 시 필요한 컨텍스트 정보를 제공합니다.

## 접속 정보

### Production (Hetzner)
```bash
# SSH를 통한 psql 접속
ssh root@157.180.72.0 "docker exec -it buddhakorea-postgres psql -U postgres -d buddhakorea"

# 단일 쿼리 실행
ssh root@157.180.72.0 "docker exec buddhakorea-postgres psql -U postgres -d buddhakorea -c \"SELECT * FROM users;\""
```

### Docker 컨테이너
| 컨테이너 이름 | 용도 |
|-------------|------|
| buddhakorea-postgres | PostgreSQL 데이터베이스 |
| buddhakorea-backend | FastAPI 백엔드 |
| buddhakorea-nginx | Nginx 리버스 프록시 |
| buddhakorea-redis | Redis 캐시/세션 |

---

## 테이블 스키마

### 1. users (회원)

회원 정보를 저장하는 테이블.

```sql
CREATE TABLE users (
    id               SERIAL PRIMARY KEY,
    email            VARCHAR,                          -- 이메일 (unique)
    nickname         VARCHAR,                          -- 닉네임/표시 이름
    provider         VARCHAR,                          -- OAuth 제공자 (google, naver, kakao)
    social_id        VARCHAR,                          -- OAuth 제공자의 사용자 ID
    profile_img      VARCHAR,                          -- 프로필 이미지 URL
    created_at       TIMESTAMP,                        -- 가입 일시
    last_login       TIMESTAMP,                        -- 마지막 로그인 일시
    role             VARCHAR(20) DEFAULT 'user',       -- 역할 (user, admin)
    is_active        BOOLEAN DEFAULT true,             -- 활성화 상태
    daily_chat_limit INTEGER DEFAULT 50,               -- 일일 채팅 제한
    updated_at       TIMESTAMP
);

-- 인덱스
CREATE UNIQUE INDEX ix_users_email ON users(email);
CREATE INDEX ix_users_id ON users(id);
CREATE INDEX ix_users_social_id ON users(social_id);
```

**조회 예시:**
```sql
-- 최근 가입 회원 조회
SELECT id, email, nickname, provider, created_at, last_login
FROM users
ORDER BY created_at DESC;

-- 특정 기간 가입 회원 수
SELECT COUNT(*) FROM users
WHERE created_at >= '2025-12-01';
```

---

### 2. social_accounts (소셜 계정 연동)

한 사용자가 여러 소셜 계정을 연동할 수 있도록 지원.

```sql
CREATE TABLE social_accounts (
    id               SERIAL PRIMARY KEY,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider         VARCHAR(20) NOT NULL,             -- google, naver, kakao
    provider_user_id VARCHAR(255) NOT NULL,            -- 제공자별 고유 ID
    provider_email   VARCHAR(255),                     -- 제공자 이메일
    access_token     TEXT,                             -- OAuth access token
    refresh_token    TEXT,                             -- OAuth refresh token
    token_expires_at TIMESTAMP WITH TIME ZONE,
    raw_profile      JSON,                             -- 제공자에서 받은 전체 프로필
    created_at       TIMESTAMP WITH TIME ZONE,
    last_used_at     TIMESTAMP WITH TIME ZONE
);

-- 인덱스
CREATE INDEX ix_social_accounts_user_id ON social_accounts(user_id);
CREATE UNIQUE INDEX uq_provider_user_id ON social_accounts(provider, provider_user_id);
CREATE UNIQUE INDEX uq_user_provider ON social_accounts(user_id, provider);
```

---

### 3. user_usage (회원 사용량 추적)

로그인 사용자의 일일 사용량 추적.

```sql
CREATE TABLE user_usage (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    usage_date  DATE NOT NULL,                        -- 사용 날짜
    chat_count  INTEGER,                              -- 채팅 횟수
    tokens_used INTEGER,                              -- 사용 토큰 수
    created_at  TIMESTAMP WITH TIME ZONE,
    updated_at  TIMESTAMP WITH TIME ZONE
);

-- 인덱스
CREATE UNIQUE INDEX uq_user_usage_date ON user_usage(user_id, usage_date);
CREATE INDEX ix_user_usage_user_id ON user_usage(user_id);
```

---

### 4. anonymous_usage (비로그인 사용량 추적)

비로그인 사용자의 일일 사용량을 IP 해시로 추적.

```sql
CREATE TABLE anonymous_usage (
    id         SERIAL PRIMARY KEY,
    ip_hash    VARCHAR(64) NOT NULL,                  -- IP 해시 (개인정보 보호)
    usage_date DATE NOT NULL,
    chat_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
);

-- 인덱스
CREATE UNIQUE INDEX uq_anon_ip_date ON anonymous_usage(ip_hash, usage_date);
CREATE INDEX ix_anonymous_usage_ip_hash ON anonymous_usage(ip_hash);
```

---

### 5. chat_sessions (채팅 세션)

사용자 채팅 세션 관리.

```sql
CREATE TABLE chat_sessions (
    id              SERIAL PRIMARY KEY,
    session_uuid    VARCHAR(36),                      -- 클라이언트용 UUID
    user_id         INTEGER REFERENCES users(id),     -- NULL이면 비로그인
    title           VARCHAR(200),                     -- 세션 제목 (자동 생성)
    created_at      TIMESTAMP,
    last_message_at TIMESTAMP,
    is_active       BOOLEAN,
    summary         TEXT,                             -- 대화 요약
    is_archived     BOOLEAN DEFAULT false,
    message_count   INTEGER DEFAULT 0,
    deleted_at      TIMESTAMP                         -- soft delete
);

-- 인덱스
CREATE UNIQUE INDEX ix_chat_sessions_session_uuid ON chat_sessions(session_uuid);
CREATE INDEX ix_chat_sessions_user_id ON chat_sessions(user_id);
```

---

### 6. chat_messages (채팅 메시지)

각 채팅 메시지 저장.

```sql
CREATE TABLE chat_messages (
    id            SERIAL PRIMARY KEY,
    session_id    INTEGER NOT NULL REFERENCES chat_sessions(id),
    role          VARCHAR(20) NOT NULL,               -- user, assistant, system
    content       TEXT NOT NULL,                      -- 메시지 내용
    model_used    VARCHAR(50),                        -- 사용된 LLM 모델
    sources_count INTEGER,                            -- RAG 소스 개수
    response_mode VARCHAR(20),                        -- 응답 모드
    created_at    TIMESTAMP
);

-- 인덱스
CREATE INDEX ix_chat_messages_session_id ON chat_messages(session_id);
```

---

### 7. literatures (빠알리 문헌)

번역 대상 빠알리 문헌 목록.

```sql
CREATE TABLE literatures (
    id                  VARCHAR(100) PRIMARY KEY,     -- 예: kn-dhammapada-atthakatha
    name                VARCHAR(255) NOT NULL,        -- 한글명: 법구경 주석서
    pali_name           VARCHAR(255) NOT NULL,        -- 빠알리명: Dhammapada-aṭṭhakathā
    pitaka              VARCHAR(50) NOT NULL,         -- 삼장: Sutta/Vinaya/Abhidhamma Piṭaka
    nikaya              VARCHAR(100),                 -- 니까야 분류
    status              VARCHAR(20),                  -- 상태
    total_segments      INTEGER,                      -- 총 세그먼트 수
    translated_segments INTEGER,                      -- 번역 완료 세그먼트 수
    source_pdf          VARCHAR(255),                 -- 원본 PDF 파일명
    hierarchy_labels    JSONB,                        -- 계층 구조 레이블
    display_metadata    JSONB DEFAULT '{}',           -- 표시용 메타데이터
    created_at          TIMESTAMP,
    updated_at          TIMESTAMP
);
```

**문헌 ID 명명 규칙:**
- `{장-부약어}-{문헌명}-atthakatha`
- 장(Piṭaka) 약어: `dn`(장부), `mn`(중부), `sn`(상윳따), `an`(앙굿따라), `kn`(소부), `vin`(율장), `abhi`(논장)

**현재 등록 문헌 수:** 47개

---

### 8. segments (문헌 세그먼트)

각 문헌의 번역 단위 세그먼트.

```sql
CREATE TABLE segments (
    id            SERIAL PRIMARY KEY,
    literature_id VARCHAR(100) NOT NULL REFERENCES literatures(id) ON DELETE CASCADE,
    vagga_id      INTEGER,                            -- 품(vagga) ID
    vagga_name    VARCHAR(255),                       -- 품 이름
    sutta_id      INTEGER,                            -- 경(sutta) ID
    sutta_name    VARCHAR(255),                       -- 경 이름
    page_number   INTEGER,                            -- 원본 페이지 번호
    paragraph_id  INTEGER NOT NULL,                   -- 단락 ID
    original_text TEXT NOT NULL,                      -- 원문 빠알리어
    translation   JSONB,                              -- 번역 결과 (구조화)
    is_translated BOOLEAN,                            -- 번역 완료 여부
    created_at    TIMESTAMP,
    updated_at    TIMESTAMP
);

-- 인덱스
CREATE UNIQUE INDEX uq_segment_location ON segments(literature_id, vagga_id, sutta_id, paragraph_id);
CREATE INDEX idx_segments_literature ON segments(literature_id);
CREATE INDEX idx_segments_location ON segments(literature_id, vagga_id, sutta_id);
CREATE INDEX idx_segments_page ON segments(literature_id, page_number);
CREATE INDEX idx_segments_translated ON segments(is_translated);
```

**translation JSONB 구조:**
```json
{
  "summary": "이 내용에 대한 요약...",
  "sentences": [
    {
      "original_pali": "Namo tassa bhagavato...",
      "literal_translation": "직역...",
      "free_translation": "의역...",
      "explanation": "설명...",
      "grammatical_analysis": "문법 분석..."
    }
  ]
}
```

**현재 상태:**
- 총 세그먼트: 18,581개
- 번역 완료: 1,149개 (약 6.2%)

---

### 9. query_logs (질의 로그)

RAG 질의 기록.

```sql
CREATE TABLE query_logs (
    id            SERIAL PRIMARY KEY,
    session_id    VARCHAR(100),                       -- 세션 식별자
    literature_id VARCHAR(100) REFERENCES literatures(id) ON DELETE SET NULL,
    segment_id    INTEGER,                            -- 관련 세그먼트
    question      TEXT NOT NULL,                      -- 질문
    answer        TEXT,                               -- 응답
    model         VARCHAR(50),                        -- 사용 모델
    tokens_used   INTEGER,                            -- 토큰 사용량
    created_at    TIMESTAMP
);

-- 인덱스
CREATE INDEX idx_query_logs_session ON query_logs(session_id);
CREATE INDEX idx_query_logs_created ON query_logs(created_at);
```

---

## ER 다이어그램 (관계)

```
users
  ├──< social_accounts (1:N)
  ├──< user_usage (1:N)
  └──< chat_sessions (1:N)
         └──< chat_messages (1:N)

literatures
  ├──< segments (1:N)
  └──< query_logs (1:N)

anonymous_usage (독립)
```

---

## 자주 사용하는 쿼리

### 회원 관리

```sql
-- 최근 가입 회원
SELECT id, email, nickname, provider, created_at
FROM users ORDER BY created_at DESC LIMIT 20;

-- 활성 사용자 (최근 7일 로그인)
SELECT * FROM users
WHERE last_login >= NOW() - INTERVAL '7 days';

-- 제공자별 회원 수
SELECT provider, COUNT(*) FROM users GROUP BY provider;
```

### 번역 진행률

```sql
-- 문헌별 번역 진행률
SELECT
    id,
    name,
    total_segments,
    translated_segments,
    ROUND(translated_segments::numeric / NULLIF(total_segments, 0) * 100, 2) as progress_pct
FROM literatures
WHERE total_segments > 0
ORDER BY progress_pct DESC;

-- 전체 번역 진행률
SELECT
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE is_translated = true) as translated,
    ROUND(COUNT(*) FILTER (WHERE is_translated = true)::numeric / COUNT(*) * 100, 2) as pct
FROM segments;
```

### 사용량 분석

```sql
-- 일별 채팅 사용량 (로그인 유저)
SELECT usage_date, SUM(chat_count) as total_chats, SUM(tokens_used) as total_tokens
FROM user_usage
GROUP BY usage_date
ORDER BY usage_date DESC;

-- 비로그인 일별 사용량
SELECT usage_date, COUNT(DISTINCT ip_hash) as unique_users, SUM(chat_count) as total_chats
FROM anonymous_usage
GROUP BY usage_date
ORDER BY usage_date DESC;
```

---

## 개발 시 주의사항

### 1. 타임존
- `TIMESTAMP`: 타임존 없음 (서버 로컬 시간 가정)
- `TIMESTAMP WITH TIME ZONE`: 타임존 포함
- 일관성을 위해 UTC 사용 권장

### 2. Soft Delete
- `chat_sessions.deleted_at`: soft delete 구현
- 실제 삭제 시 CASCADE 주의

### 3. JSONB 필드
- `segments.translation`: 번역 결과 구조화 저장
- `literatures.hierarchy_labels`: 문헌 계층 구조
- JSONB 연산자: `->>`, `->`, `@>`, `?`

### 4. 외래 키
- `ON DELETE CASCADE`: social_accounts, user_usage, segments
- `ON DELETE SET NULL`: query_logs.literature_id

### 5. 유니크 제약
- `users.email`: 중복 불가
- `(ip_hash, usage_date)`: 일별 단일 레코드
- `(user_id, usage_date)`: 일별 단일 레코드
- `(literature_id, vagga_id, sutta_id, paragraph_id)`: 세그먼트 위치

---

## 마이그레이션 이력

현재 Alembic 또는 별도 마이그레이션 도구 미사용. 스키마 변경 시 직접 ALTER 수행.

---

## 백업

```bash
# 전체 백업
ssh root@157.180.72.0 "docker exec buddhakorea-postgres pg_dump -U postgres buddhakorea > /backup/buddhakorea_$(date +%Y%m%d).sql"

# 특정 테이블만
ssh root@157.180.72.0 "docker exec buddhakorea-postgres pg_dump -U postgres -t users -t social_accounts buddhakorea"
```

---

*마지막 업데이트: 2025-12-26*
