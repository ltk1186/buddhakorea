# Authentication & Login Testing Plan

## Application Overview

The Buddha Korea application features OAuth 2.0 authentication with multiple social providers (Google, Naver, Kakao). The system supports both authenticated users and anonymous access. Key authentication components include: OAuth login endpoints (/auth/login/{provider}), OAuth callback handling (/auth/callback/{provider}), CSRF state management via Redis, JWT token pairs (15-min access tokens + 7-day refresh tokens), user profile management, and logout functionality. The frontend has a mypage.html that displays user information and manages authentication state.

## Test Scenarios

### 1. OAuth Login Flow

**Seed:** `tests/auth-login.seed.ts`

#### 1.1. User can initiate Google OAuth login

**File:** `tests/auth-login/google-login-initiate.spec.ts`

**Steps:**
  1. Navigate to mypage.html
  2. Verify 'Login' button is visible when not authenticated
  3. Click on login link (without Google redirect expected in test)
  4. Verify redirect URL structure contains /auth/login/google

**Expected Results:**
  - Login button is visible and clickable
  - URL preparation is correct for OAuth flow
  - No authentication errors are displayed

#### 1.2. User can initiate Naver OAuth login

**File:** `tests/auth-login/naver-login-initiate.spec.ts`

**Steps:**
  1. Navigate to mypage.html
  2. Verify 'Login' button is visible when not authenticated
  3. Click on Naver login option
  4. Verify redirect URL structure contains /auth/login/naver

**Expected Results:**
  - Login button redirects to Naver OAuth endpoint
  - URL includes proper redirect_uri parameter
  - No authentication errors during redirect

#### 1.3. CSRF state validation is performed

**File:** `tests/auth-login/csrf-protection.spec.ts`

**Steps:**
  1. Attempt to access /auth/callback/google with missing state parameter
  2. Attempt to access /auth/callback/google with invalid state parameter
  3. Attempt to access /auth/callback/google with valid state parameter (simulated)
  4. Verify error handling for missing/invalid state

**Expected Results:**
  - Invalid state returns auth error redirect
  - Missing state is handled gracefully
  - Valid state allows callback to proceed

#### 1.4. OAuth callback handles user creation

**File:** `tests/auth-login/user-creation-on-callback.spec.ts`

**Steps:**
  1. Simulate successful OAuth callback with new user data
  2. Verify user record is created in database
  3. Verify social account record is created
  4. Verify JWT tokens are generated
  5. Verify user is set as active

**Expected Results:**
  - New user is created with correct email and nickname
  - Social account is linked to user
  - Access and refresh tokens are issued
  - User status is set to active

#### 1.5. OAuth callback handles existing user

**File:** `tests/auth-login/existing-user-callback.spec.ts`

**Steps:**
  1. Set up a pre-existing user with social account
  2. Simulate OAuth callback with same user data
  3. Verify user record is not duplicated
  4. Verify social account association is maintained
  5. Verify last_login timestamp is updated

**Expected Results:**
  - User record remains singular (no duplicates)
  - Social account binding is preserved
  - Last login time is updated to current time

#### 1.6. JWT access token is set in cookies after login

**File:** `tests/auth-login/token-cookie-handling.spec.ts`

**Steps:**
  1. Simulate successful OAuth callback
  2. Verify access_token cookie is set
  3. Verify refresh_token cookie is set
  4. Verify cookie security attributes (httpOnly, secure, sameSite)
  5. Verify token expiration settings

**Expected Results:**
  - Access token cookie is present and readable by server only
  - Refresh token cookie is present and readable by server only
  - Cookies have secure flag set in production
  - Cookies have sameSite=lax for OAuth flow
  - Access token expires in 15 minutes
  - Refresh token expires in 7 days

#### 1.7. Multiple OAuth provider links

**File:** `tests/auth-login/multiple-provider-links.spec.ts`

**Steps:**
  1. Create user with Google OAuth
  2. Log in to mypage
  3. Verify option to link additional providers
  4. Link Naver account to same user
  5. Verify both social accounts are associated
  6. Verify primary provider is correctly set

**Expected Results:**
  - User can have multiple social accounts linked
  - All providers are listed in social accounts section
  - Primary provider is the first linked account
  - User can manage linked accounts

#### 1.8. User can view profile after login

**File:** `tests/auth-login/profile-view-after-login.spec.ts`

**Steps:**
  1. Simulate successful OAuth login
  2. Navigate to mypage.html
  3. Verify user information is displayed
  4. Verify usage statistics are shown
  5. Verify logout option is available

**Expected Results:**
  - User nickname is displayed correctly
  - User email is shown if available
  - Daily usage stats are visible
  - Logout button is present and clickable

### 2. Login UI & Session Management

**Seed:** `tests/auth-login-ui.seed.ts`

#### 2.1. Login button displays when not authenticated

**File:** `tests/auth-login-ui/login-button-unauthenticated.spec.ts`

**Steps:**
  1. Open mypage.html without authentication
  2. Verify login button text is '로그인'
  3. Verify button links to /auth/login/google
  4. Verify no user information is displayed

**Expected Results:**
  - Login prompt is visible
  - Login button is properly styled
  - Links to correct OAuth endpoint

#### 2.2. User profile displays when authenticated

**File:** `tests/auth-login-ui/profile-display-authenticated.spec.ts`

**Steps:**
  1. Set authentication cookies (simulated login)
  2. Open mypage.html
  3. Verify user nickname is displayed
  4. Verify logout button is visible
  5. Verify login button is hidden

**Expected Results:**
  - User profile section is displayed
  - User nickname appears correctly
  - Logout button replaces login button
  - Auth container shows user info

#### 2.3. Loading state displays correctly

**File:** `tests/auth-login-ui/loading-state.spec.ts`

**Steps:**
  1. Open mypage.html
  2. Observe initial loading state
  3. Wait for user data to load
  4. Verify loading spinner disappears
  5. Verify content is displayed

**Expected Results:**
  - Loading spinner is visible initially
  - Loading message displays
  - Spinner disappears when content loads
  - No broken layouts during transition

#### 2.4. Not logged in state displays fallback

**File:** `tests/auth-login-ui/not-logged-in-fallback.spec.ts`

**Steps:**
  1. Open mypage.html without authentication
  2. Wait for fetch to complete
  3. Verify not-logged-in card is displayed
  4. Verify login button is visible
  5. Verify navigation back to home works

**Expected Results:**
  - Fallback UI is shown when user is not logged in
  - Login prompt is clear and actionable
  - User can navigate away

#### 2.5. Error state handles connection failures

**File:** `tests/auth-login-ui/error-state-handling.spec.ts`

**Steps:**
  1. Mock API failure for /api/users/me endpoint
  2. Open mypage.html
  3. Verify error message displays
  4. Verify user can navigate home
  5. Verify page gracefully handles network error

**Expected Results:**
  - Error message is user-friendly
  - Navigation options are provided
  - No console errors are thrown

#### 2.6. Auth container updates dynamically on header

**File:** `tests/auth-login-ui/header-auth-container.spec.ts`

**Steps:**
  1. Open any page with header (index.html)
  2. Verify auth container shows login link
  3. Simulate authentication
  4. Verify auth container updates to show username
  5. Verify logout link is present

**Expected Results:**
  - Header auth container updates without page reload
  - User status is reflected in header
  - Login/logout transitions work smoothly

#### 2.7. Responsive layout for mobile auth UI

**File:** `tests/auth-login-ui/responsive-auth-mobile.spec.ts`

**Steps:**
  1. Set viewport to mobile (≤768px)
  2. Open mypage.html with login prompt
  3. Verify login button is accessible
  4. Verify text sizes are readable
  5. Verify layout is not broken
  6. Set viewport to desktop
  7. Verify layout adapts correctly

**Expected Results:**
  - Mobile layout is usable
  - Touch targets are appropriately sized
  - Text is readable without scaling
  - Desktop layout differs appropriately

### 3. Logout Functionality

**Seed:** `tests/auth-logout.seed.ts`

#### 3.1. User can logout from mypage

**File:** `tests/auth-logout/logout-from-mypage.spec.ts`

**Steps:**
  1. Log in user (simulate)
  2. Navigate to mypage.html
  3. Click logout button
  4. Verify logout POST request is sent to /auth/logout
  5. Verify redirect to index.html

**Expected Results:**
  - Logout request is sent with credentials
  - HTTP 200 or similar success response
  - User is redirected to home page
  - Cookies are cleared

#### 3.2. Logout clears authentication cookies

**File:** `tests/auth-logout/clear-cookies-on-logout.spec.ts`

**Steps:**
  1. Log in user (simulate with cookies)
  2. Verify access_token cookie exists
  3. Click logout button
  4. Verify access_token cookie is deleted
  5. Verify refresh_token cookie is deleted

**Expected Results:**
  - Both token cookies are removed
  - Subsequent requests show unauthenticated state

#### 3.3. User cannot access protected endpoints after logout

**File:** `tests/auth-logout/protected-endpoint-after-logout.spec.ts`

**Steps:**
  1. Log in and set session
  2. Access /api/users/me (should succeed)
  3. Log out
  4. Attempt to access /api/users/me again
  5. Verify 401 or 403 response

**Expected Results:**
  - Protected endpoints reject requests after logout
  - Session is properly invalidated

#### 3.4. Logout is available in all authenticated pages

**File:** `tests/auth-logout/logout-in-all-pages.spec.ts`

**Steps:**
  1. Log in user
  2. Navigate to various pages (chat.html, teaching.html, etc.)
  3. Verify logout button is present on each page
  4. Click logout on different pages
  5. Verify logout works from any page

**Expected Results:**
  - Logout option is consistently available
  - Logout works from any page
  - User is redirected appropriately after logout

#### 3.5. User is logged out on session expiration

**File:** `tests/auth-logout/session-expiration.spec.ts`

**Steps:**
  1. Log in user
  2. Let session remain idle for extended period
  3. Attempt to make API request
  4. Verify token is expired
  5. Verify system redirects to login

**Expected Results:**
  - Expired access token triggers re-authentication
  - User is not stuck with invalid session
  - Clear re-login prompt is shown

### 4. JWT Token Management

**Seed:** `tests/auth-tokens.seed.ts`

#### 4.1. Access token is validated on protected endpoints

**File:** `tests/auth-tokens/access-token-validation.spec.ts`

**Steps:**
  1. Log in user (get access token)
  2. Make request to /api/users/me with valid token
  3. Verify request succeeds
  4. Make request with modified token payload
  5. Verify request fails with 401

**Expected Results:**
  - Valid tokens are accepted
  - Invalid/tampered tokens are rejected
  - No unauthorized access

#### 4.2. Refresh token is used to get new access token

**File:** `tests/auth-tokens/refresh-token-endpoint.spec.ts`

**Steps:**
  1. Log in user (get refresh token)
  2. Call /auth/refresh endpoint with refresh_token
  3. Verify new access_token is returned
  4. Verify new access_token works for protected endpoints

**Expected Results:**
  - Refresh endpoint returns new access token
  - New token is valid and usable
  - Original refresh token remains valid for future refreshes

#### 4.3. Access token expires after 15 minutes

**File:** `tests/auth-tokens/access-token-expiration.spec.ts`

**Steps:**
  1. Log in user (get access token with created time)
  2. Verify token has exp claim set to ~15 minutes from iat
  3. Decode token and verify exp timestamp
  4. Wait until token would be expired (simulated)
  5. Verify expired token is rejected

**Expected Results:**
  - Access token includes exp claim
  - Exp time is approximately 15 minutes from issue
  - Expired tokens are rejected by endpoints

#### 4.4. Refresh token expires after 7 days

**File:** `tests/auth-tokens/refresh-token-expiration.spec.ts`

**Steps:**
  1. Log in user (get refresh token with created time)
  2. Verify token has exp claim set to ~7 days from iat
  3. Decode token and verify exp timestamp

**Expected Results:**
  - Refresh token includes exp claim
  - Exp time is approximately 7 days from issue

#### 4.5. Token payload includes required claims

**File:** `tests/auth-tokens/token-payload-validation.spec.ts`

**Steps:**
  1. Log in user (get tokens)
  2. Decode access token (without verification for inspection)
  3. Verify access_token includes: user_id, sub (email), type='access', iat, exp
  4. Decode refresh token
  5. Verify refresh_token includes: user_id, type='refresh', iat, exp

**Expected Results:**
  - Access token has all required claims
  - Refresh token has all required claims
  - Token structure matches security requirements

#### 4.6. Separate keys for access and refresh tokens

**File:** `tests/auth-tokens/token-key-separation.spec.ts`

**Steps:**
  1. Verify backend uses different secrets for access vs refresh
  2. Attempt to use refresh_token_secret to decode access token
  3. Attempt to use access_token_secret to decode refresh token
  4. Verify both attempts fail

**Expected Results:**
  - Token verification requires correct secret
  - Access tokens cannot be decoded with refresh secret
  - Refresh tokens cannot be decoded with access secret

#### 4.7. Token claims are properly verified

**File:** `tests/auth-tokens/token-claim-verification.spec.ts`

**Steps:**
  1. Create token with missing required claims
  2. Create token with incorrect type claim
  3. Create token with invalid signature
  4. Attempt to use malformed tokens in protected endpoint

**Expected Results:**
  - Tokens without required claims are rejected
  - Tokens with incorrect type are rejected
  - Tampered signatures are detected and rejected

### 5. User Profile & Data Management

**Seed:** `tests/auth-user-profile.seed.ts`

#### 5.1. User profile includes all required fields

**File:** `tests/auth-user-profile/profile-fields.spec.ts`

**Steps:**
  1. Log in user
  2. Call /api/users/me endpoint
  3. Verify response includes: id, email, nickname, profile_img, role, created_at, last_login

**Expected Results:**
  - All user fields are returned
  - Profile image URL is valid or null
  - Timestamps are in ISO format

#### 5.2. User daily_chat_limit is applied correctly

**File:** `tests/auth-user-profile/daily-limit-enforcement.spec.ts`

**Steps:**
  1. Create user with default limit (20)
  2. Make 20 chat requests
  3. Verify 21st request is blocked
  4. Verify error message mentions limit

**Expected Results:**
  - Users are limited to daily_chat_limit requests
  - Limit resets daily
  - Clear error message is provided

#### 5.3. User can have custom daily_chat_limit

**File:** `tests/auth-user-profile/custom-limit.spec.ts`

**Steps:**
  1. Create admin user with custom limit (50)
  2. Grant higher limit to specific user
  3. Make 50 requests with that user
  4. Verify 51st request is blocked

**Expected Results:**
  - Custom limits override defaults
  - Higher limits are enforced correctly

#### 5.4. User role is correctly assigned

**File:** `tests/auth-user-profile/user-roles.spec.ts`

**Steps:**
  1. Create regular user (role='user')
  2. Create admin user (role='admin')
  3. Create beta tester (role='beta')
  4. Verify role is persisted in database
  5. Verify role affects feature access appropriately

**Expected Results:**
  - Roles are assigned and persisted
  - Different roles have appropriate permissions

#### 5.5. User is_active status is respected

**File:** `tests/auth-user-profile/active-status.spec.ts`

**Steps:**
  1. Create active user (is_active=true)
  2. Log in with active user
  3. Deactivate user (is_active=false)
  4. Attempt to use protected endpoints with inactive user

**Expected Results:**
  - Active users can access protected endpoints
  - Inactive users are denied access
  - Clear message is shown for inactive accounts

#### 5.6. User last_login is updated on each login

**File:** `tests/auth-user-profile/last-login-tracking.spec.ts`

**Steps:**
  1. Create user and note last_login timestamp
  2. Log out user
  3. Wait a few seconds
  4. Log in again
  5. Verify last_login is updated to new time

**Expected Results:**
  - Last login timestamp is updated
  - Timestamp reflects actual login time
  - Previous login time is overwritten

#### 5.7. User social accounts are linked correctly

**File:** `tests/auth-user-profile/social-accounts.spec.ts`

**Steps:**
  1. Log in with Google
  2. Verify social_accounts array contains Google entry
  3. Link Naver account
  4. Verify social_accounts array contains both entries
  5. Verify provider and social_id are correct

**Expected Results:**
  - Multiple social accounts are linked to user
  - Each account has provider and social_id
  - Primary provider can be determined

#### 5.8. User data is persisted across sessions

**File:** `tests/auth-user-profile/data-persistence.spec.ts`

**Steps:**
  1. Log in and create user session
  2. Close browser/session
  3. Log in again with same credentials
  4. Verify all user data is intact

**Expected Results:**
  - User profile survives session restart
  - All data is persisted in database

#### 5.9. User can view usage statistics

**File:** `tests/auth-user-profile/usage-stats.spec.ts`

**Steps:**
  1. Log in user
  2. Navigate to mypage.html
  3. Verify usage stats are displayed (X/20 requests)
  4. Call chat endpoint
  5. Refresh mypage
  6. Verify usage count increased

**Expected Results:**
  - Usage statistics are displayed accurately
  - Stats update after API calls
  - Visual representation is clear
