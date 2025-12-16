// ========================================
// 전자 사경 데이터 모듈 (JSON 로딩 버전)
// Buddha Korea - Sutra Copying Data
// ========================================

let SUTRA_DATA = {};
let CATEGORIES = {};
let CATEGORY_ANIMATIONS = {};

/**
 * Helper function to generate repeated text
 * @param {string} pattern - Text pattern to repeat
 * @param {number} count - Number of repetitions
 * @returns {string} - Joined text with spaces
 */
function generateRepeatedText(pattern, count) {
    return Array(count).fill(pattern).join(' ');
}

/**
 * Load and process sutra data from JSON
 */
async function loadSutraData() {
    try {
        const response = await fetch('data/sutras.json');
        if (!response.ok) {
            throw new Error(`Failed to load sutras.json: ${response.status}`);
        }

        const data = await response.json();

        // Store categories and animations
        CATEGORIES = data.categories;
        CATEGORY_ANIMATIONS = data.categoryAnimations;

        // Process sutras
        SUTRA_DATA = {};
        for (const [key, sutra] of Object.entries(data.sutras)) {
            SUTRA_DATA[key] = { ...sutra };

            // Generate text for pattern-based sutras (mantras, names)
            if (sutra.pattern && sutra.repeat) {
                SUTRA_DATA[key].text = generateRepeatedText(sutra.pattern, sutra.repeat);
            }

            // Add length getter
            Object.defineProperty(SUTRA_DATA[key], 'length', {
                get: function() { return this.text.length; },
                enumerable: false
            });
        }

        console.log('✅ Sutra data loaded successfully - 12 sutras');
        return true;
    } catch (error) {
        console.error('❌ Failed to load sutra data:', error);
        throw error;
    }
}

/**
 * Helper functions
 */
export function getSutraById(id) {
    const sutra = SUTRA_DATA[id];
    if (!sutra) {
        console.error(`Sutra not found: ${id}`);
        return null;
    }
    return sutra;
}

export function getSutrasByCategory(category) {
    if (category === 'all') {
        return Object.values(SUTRA_DATA).sort((a, b) => a.order - b.order);
    }

    return Object.values(SUTRA_DATA)
        .filter(s => s.category === category)
        .sort((a, b) => a.order - b.order);
}

export function getCategoryLabel(category) {
    return CATEGORIES[category]?.label || category;
}

export function getAnimationClass(category) {
    return CATEGORY_ANIMATIONS[category] || 'char-fade';
}

// Initialize data loading
const dataLoadedPromise = loadSutraData();

// Export data access (will be populated after load)
export { SUTRA_DATA, CATEGORIES, CATEGORY_ANIMATIONS, dataLoadedPromise };

// Backward compatibility alias
export const SUTRAS = SUTRA_DATA;
