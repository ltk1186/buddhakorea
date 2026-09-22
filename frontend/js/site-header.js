// Shared by the static website and the React reader. Shadow DOM keeps page-specific
// CSS from changing the site's navigation, including on the chat screen.
(() => {
    if (customElements.get('buddha-site-header')) return;
    const script = document.currentScript;
    const siteRoot = window.location.protocol === 'file:'
        ? 'http://127.0.0.1:8011/'
        : new URL('/', window.location.href).href;
    const assetRoot = script ? new URL('../', script.src).href : siteRoot;
    const apiRoot = () => window.Auth?.API_BASE_URL ?? window.API_BASE_URL
        ?? (['localhost', '127.0.0.1'].includes(window.location.hostname) ? 'http://localhost:8000' : '');

    class BuddhaSiteHeader extends HTMLElement {
        connectedCallback() {
            if (this.shadowRoot) return;
            const root = this.attachShadow({ mode: 'open' });
            root.innerHTML = `
                <style>:host { display:block; height:70px; flex-shrink:0; } :host([overlay]) { height:0; } @media(max-width:767px) { :host { height:60px; } }</style>
                <link rel="stylesheet" href="${assetRoot}css/site-header.css?v=20260910">
                <header>
                    <div class="container">
                        <a class="logo" href="${siteRoot}index.html" aria-label="Buddha Korea 홈">
                            <img src="${assetRoot}assets/buddha-line.png" alt="" width="32">
                            <span>Buddha Korea</span>
                        </a>
                        <nav aria-label="주요 메뉴">
                            <a href="${siteRoot}pali/" data-section="reading">경전 읽기</a>
                            <a href="${siteRoot}chat.html" data-section="chat">AI 채팅 시작</a>
                            <a href="${siteRoot}sutra-writing.html" data-section="writing">사경</a>
                            <span class="auth"><a class="login" href="${siteRoot}index.html?showLogin=true">로그인</a></span>
                        </nav>
                    </div>
                </header>`;
            const path = window.location.pathname;
            const section = path.includes('/pali/') ? 'reading' : path.endsWith('/chat.html') ? 'chat' : path.endsWith('/sutra-writing.html') ? 'writing' : '';
            root.querySelector(`[data-section="${section}"]`)?.setAttribute('aria-current', 'page');
            root.querySelector('.login').addEventListener('click', (event) => {
                if (typeof window.showLoginModal === 'function') {
                    event.preventDefault();
                    window.showLoginModal();
                }
            });
            void this.updateAuth();
        }

        async updateAuth() {
            try {
                let user;
                if (window.Auth) {
                    user = await window.Auth.checkAuthStatus();
                } else {
                    const base = apiRoot();
                    let response = await fetch(`${base}/api/users/me`, { credentials: 'include' });
                    if (response.status === 401) {
                        const refresh = await fetch(`${base}/auth/refresh`, { method: 'POST', credentials: 'include' });
                        if (refresh.ok) response = await fetch(`${base}/api/users/me`, { credentials: 'include' });
                    }
                    if (response.ok) user = await response.json();
                }
                if (!user || !this.isConnected) return;
                const account = document.createElement('a');
                account.href = `${siteRoot}mypage.html`;
                account.className = 'account';
                account.textContent = `${user.nickname || '회원'}님`;
                const logout = document.createElement('button');
                logout.textContent = '로그아웃';
                logout.addEventListener('click', async () => {
                    if (window.Auth) return window.Auth.logout();
                    if (typeof window.handleLogout === 'function') return window.handleLogout();
                    const response = await fetch(`${apiRoot()}/auth/logout`, { method: 'POST', credentials: 'include' });
                    if (response.ok) window.location.reload();
                });
                this.shadowRoot.querySelector('.auth').replaceChildren(account, logout);
            } catch {
                // Reading remains available when the optional account service is offline.
            }
        }
    }

    customElements.define('buddha-site-header', BuddhaSiteHeader);
})();
