/**
 * Buddha Korea - Auth Utilities
 * Handles authentication status check, silent refresh, and logout.
 */

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8000'
    : '';

async function checkAuthStatus() {
    try {
        let response = await fetch(`${API_BASE_URL}/api/users/me`, { credentials: 'include' });

        // Access token expired — try silent refresh with refresh token
        if (response.status === 401) {
            const refreshed = await fetch(`${API_BASE_URL}/auth/refresh`, {
                method: 'POST',
                credentials: 'include'
            });
            if (refreshed.ok) {
                response = await fetch(`${API_BASE_URL}/api/users/me`, { credentials: 'include' });
            }
        }

        if (response.ok) {
            return await response.json();
        }
        return null;
    } catch (e) {
        console.error("Auth check failed", e);
        return null;
    }
}

async function logout() {
    try {
        await fetch(`${API_BASE_URL}/auth/logout`, { method: 'POST', credentials: 'include' });
        window.location.reload();
    } catch (e) {
        console.error("Logout failed", e);
    }
}

// Function to update header auth UI
async function updateHeaderAuthUI(containerId, isChatPage = false) {
    const user = await checkAuthStatus();
    const container = document.getElementById(containerId);
    if (!container) return;

    container.textContent = '';
    
    if (user) {
        if (isChatPage) {
            // Chat page style (Ghosa AI)
            const userLink = document.createElement('a');
            userLink.href = 'mypage.html';
            userLink.className = 'user-link';
            userLink.textContent = user.nickname || '내 정보';
            
            const logoutLink = document.createElement('a');
            logoutLink.href = '#';
            logoutLink.className = 'logout-link';
            logoutLink.textContent = '로그아웃';
            logoutLink.addEventListener('click', (e) => {
                e.preventDefault();
                logout();
            });
            
            container.appendChild(userLink);
            container.appendChild(logoutLink);
        } else {
            // Main page style (Buddha Korea)
            const mypageLink = document.createElement('a');
            mypageLink.href = 'mypage.html';
            mypageLink.textContent = (user.nickname || '회원') + '님';
            mypageLink.style.cssText = 'font-size:0.9rem;margin-right:8px;text-decoration:none;color:var(--color-text-primary);';
            
            const logoutLink = document.createElement('a');
            logoutLink.href = '#';
            logoutLink.textContent = '로그아웃';
            logoutLink.style.cssText = 'font-size:0.85rem;color:#666;text-decoration:none;';
            logoutLink.addEventListener('click', (e) => {
                e.preventDefault();
                logout();
            });
            
            container.appendChild(mypageLink);
            container.appendChild(logoutLink);
        }
    } else {
        const loginLink = document.createElement('a');
        loginLink.href = '#';
        loginLink.textContent = '로그인';
        loginLink.className = 'nav-link login-link';
        
        if (isChatPage) {
             loginLink.style.cssText = 'background: rgba(90, 154, 110, 0.12); border-radius: 20px; padding: 6px 14px; color: var(--color-text-primary); font-weight: 600; text-decoration: none;';
             loginLink.addEventListener('click', (e) => {
                e.preventDefault();
                window.Auth.showLoginModal();
            });
        } else {
            // Main page style (Buddha Korea) - green pill
            loginLink.style.cssText = 'background: #5A9A6E; border-radius: 20px; padding: 8px 18px; color: white; font-weight: 600; font-size: 0.9rem; text-decoration: none; display: inline-flex; align-items: center;';
            loginLink.addEventListener('click', (e) => {
                e.preventDefault();
                window.Auth.showLoginModal();
            });
        }
        container.appendChild(loginLink);
    }
    
    return user;
}

function showLoginModal() {
    if (typeof window.showLoginModal === 'function') {
        window.showLoginModal();
    } else {
        // Fallback to redirecting to home with showLogin parameter
        window.location.href = '/?showLogin=true';
    }
}

// Export functions if using modules, but here we likely just include the script
window.Auth = {
    checkAuthStatus,
    logout,
    updateHeaderAuthUI,
    showLoginModal,
    API_BASE_URL
};
