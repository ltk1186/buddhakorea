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

// --- Scroll to AI Section ---
function scrollToAI(event) {
    // On mobile: redirect to main page AI section and prevent dropdown
    // On desktop: allow dropdown to open
    const isMobile = window.innerWidth <= 768;

    if (isMobile) {
        event.preventDefault();
        event.stopPropagation();

        // Check if we're on index.html
        const isIndexPage = window.location.pathname.endsWith('index.html') ||
                           window.location.pathname.endsWith('/') ||
                           window.location.pathname.includes('/buddhakorea/') && !window.location.pathname.match(/\/(sutra-writing|meditation|teaching)\.html/);

        if (isIndexPage) {
            // If on index page, scroll to AI section with optimal mobile positioning
            scrollToAISection();
        } else {
            // If on other pages, redirect to index page AI section
            window.location.href = 'index.html#ai-tools';
        }
    }
    // On desktop, do nothing - let dropdown work normally
}

// --- Scroll to AI Section with optimal mobile positioning ---
function scrollToAISection() {
    const aiSection = document.getElementById('ai-tools');
    if (!aiSection) return;

    // Get the section's position
    const sectionTop = aiSection.getBoundingClientRect().top + window.pageYOffset;

    // Calculate optimal scroll position for mobile
    // Subtract header height (60px on mobile) and add some padding for better visual positioning
    const headerHeight = 60;
    const additionalOffset = 20; // Add 20px padding from top
    const targetScrollPosition = sectionTop - headerHeight - additionalOffset;

    window.scrollTo({
        top: targetScrollPosition,
        behavior: 'smooth'
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

// --- Initialize All Features ---
function init() {
    initInteractiveLight();
    initScrollReveal();
    initAINavButton();
    handleHashNavigation();
}

// --- Initialize AI Navigation Button ---
function initAINavButton() {
    const aiNavButton = document.getElementById('ai-nav-button');
    if (aiNavButton) {
        aiNavButton.addEventListener('click', scrollToAI);
    }
}

// --- Handle hash navigation (when coming from other pages) ---
function handleHashNavigation() {
    // Check if URL has #ai-tools hash
    if (window.location.hash === '#ai-tools') {
        const isMobile = window.innerWidth <= 768;

        if (isMobile) {
            // Wait for page to fully load and render before scrolling
            setTimeout(() => {
                scrollToAISection();
            }, 100);
        } else {
            // On desktop, use default browser behavior
            const aiSection = document.getElementById('ai-tools');
            if (aiSection) {
                aiSection.scrollIntoView({ behavior: 'smooth' });
            }
        }
    }
}

// Run when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}