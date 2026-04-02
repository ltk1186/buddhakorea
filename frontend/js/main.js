// Buddha Korea - Main JavaScript

// --- Interactive Light Effect ---
function initInteractiveLight() {
    const light = document.querySelector('.interactive-light');
    
    if (!light) return;
    
    window.addEventListener('mousemove', (e) => {
        const x = e.clientX - light.offsetWidth / 2;
        const y = e.clientY - light.offsetHeight / 2;
        light.style.transform = `translate(${x}px, ${y}px)`;
    });
}

// --- Scroll Reveal Animation  ---
function initScrollReveal() {
    const revealElements = document.querySelectorAll('.reveal');

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });

    revealElements.forEach(element => {
        observer.observe(element);
    });
}

// --- Header Scroll Effect ---
function initHeaderScroll() {
    const header = document.querySelector('.site-header') || document.querySelector('.desktop-nav');
    if (!header) return;

    window.addEventListener('scroll', () => {
        if (window.scrollY > 20) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }
    });
}

// --- Initialize All Features ---
function init() {
    initInteractiveLight();
    initScrollReveal();
    initHeaderScroll();
}

// Run when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}