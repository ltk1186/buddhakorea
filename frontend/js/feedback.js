// ========================================
// Google Forms Feedback Integration
// ========================================

// Google Form URL - 여기에 실제 Google Form URL을 넣으세요!
const GOOGLE_FORM_URL = 'https://docs.google.com/forms/d/e/1FAIpQLScdtXnLYXWVNBuyhA9K2qes-att84MpgNb0dIU2yMZl8uGa0w/viewform?usp=dialog';
// 예시: 'https://forms.gle/AbCdEfGhIjKlMnOp'

// Open Google Form in new tab
function openFeedbackModal() {
    if (GOOGLE_FORM_URL === 'YOUR_GOOGLE_FORM_URL_HERE') {
        alert('Google Form URL이 설정되지 않았습니다.\njs/feedback.js 파일에서 GOOGLE_FORM_URL을 설정해주세요.');
        return;
    }

    // 새 창/탭에서 Google Form 열기
    window.open(GOOGLE_FORM_URL, '_blank');
}

// Make function available globally
window.openFeedbackModal = openFeedbackModal;

// Unused functions kept for compatibility (can be removed)
function closeFeedbackModal() {
    // Not needed with Google Forms
}
window.closeFeedbackModal = closeFeedbackModal;