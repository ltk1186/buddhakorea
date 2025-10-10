// ========================================
// 전자 사경 데이터 모듈
// Buddha Korea - Sutra Copying Data
// ========================================

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
 * Category configuration
 */
export const CATEGORIES = {
    all: { label: '전체', order: 0 },
    sutra: { label: '경전', order: 1 },
    mantra: { label: '진언', order: 2 },
    name: { label: '명호', order: 3 },
    verse: { label: '게송', order: 4 }
};

/**
 * Category-specific animation mappings
 */
export const CATEGORY_ANIMATIONS = {
    sutra: 'char-fade',           // Existing smokeAscend animation
    mantra: 'char-radiate',        // NEW: Blessing radiation
    name: 'char-pureland',         // NEW: Pure Land ascent
    verse: 'char-fade'             // Reuse existing
};

/**
 * Sutra text data (10 total)
 */
export const SUTRA_DATA = {
    // ========================================
    // 경전 (Sutras) - 2 existing
    // ========================================
    metta: {
        id: 'metta',
        category: 'sutra',
        title: '자애경',
        subtitle: '慈愛經',
        description: '자애의 마음을 기르는 경전',
        text: `도닦음에 능숙한 자, 고요한 경지를 체험하면서 이처럼 행할지라.
유능하고 정직하고 진솔하며 고운 말에 온화하고 겸손하네.
만족하고 공양하기 쉽고 일 없고 검소하며
감관은 고요하여 슬기롭고 거만 떨지 않고 신도 집에 집착하지 않네.
현자가 나무랄 일은 그 어떤 것도 하지 않으니
원컨대 모든 중생 즐겁고 안녕하여 부디 행복할지라.
약하거나 강하거나 길거나 크거나 중간치이거나
짧거나 작거나 통통하거나 살아있는 생명이라면 모두 다
보이거나 보이지 않거나 멀리 있거나 가까이 있거나
태어났거나 앞으로 태어날, 그 모든 중생 부디 행복할지라.
남을 속이지 않고, 어떤 곳에서 어떤 이라도 경멸하지 않으며
성냄과 적개심으로 남의 불행을 바라지 않네.
어머니가 하나 밖에 없는 친아들을 목숨으로 보호하듯
모든 중생들을 향해 한량없는 마음을 개발할지라.
온 세상 위, 아래, 옆으로 장애와 원한과 증오를 넘어
한량없는 자애의 마음을 개발할지라.
섰거나 걷거나 앉았거나 누웠거나 깨어있을 때는 언제나
이 자애의 마음챙김을 개발할지니, 이를 일러 거룩한 삶이라 하네.
계행을 지닌 자, 사견을 따르지 않고 바른 견을 구족하여
감각적 욕망에 집착을 버려 다시는 모태에 들지 않으리라.`,
        get length() { return this.text.length; },
        estimatedTime: '8-12분',
        order: 1
    },

    mangala: {
        id: 'mangala',
        category: 'sutra',
        title: '행복경',
        subtitle: '吉祥經',
        description: '참된 행복으로 가는 길',
        text: `이와 같이 나는 들었다. 한 때 세존께서 사왓티의 제따 숲에 있는 급고독원에 머무셨다.
그 때 밤이 아주 깊어갈 즈음 어떤 천신이 아름다운 모습으로 제따 숲을 두루 환하게 밝히면서 세존께 다가왔다.
와서는 세존께 절을 올리고 한 곁에 섰다. 한 곁에 서서 그 천신은 세존께 시로써 이와 같이 말씀드렸다.
많은 천신들과 사람들은 안녕을 바라면서 행복에 대해 생각합니다.
무엇이 으뜸가는 행복인지 말씀해주십시오.
어리석은 사람을 섬기지 않고 현명한 사람을 섬기며 예경할 만한 사람을 예경하는 것, 이것이 으뜸가는 행복이라네.
그러한 적절한 곳에서 살고 일찍이 공덕을 쌓으며 자신을 바르게 확립하는 것, 이것이 으뜸가는 행복이라네.
많이 배우고 기술을 익히며 계행을 철저히 지니고 고운 말을 하는 것, 이것이 으뜸가는 행복이라네.
아버지와 어머니를 봉양하고 아내와 자식을 돌보며 생업에 충실한 것, 이것이 으뜸가는 행복이라네.
베풀고 여법하게 행하며 친척들을 보호하고 비난받을 일이 없는 행위를 하는 것, 이것이 으뜸가는 행복이라네.
불선법을 피하고 여의며 술 마시는 것을 절제하고 선법들을 향해 게으르지 않는 것, 이것이 으뜸가는 행복이라네.
존경하고 겸손하며 만족할 줄 알고 은혜를 알며 시시각각 가르침을 듣는 것, 이것이 으뜸가는 행복이라네.
인내하고 [도반의 말에] 순응하며 출가자를 만나고 때에 맞춰 법을 담론하는 것, 이것이 으뜸가는 행복이라네.
감각 기능을 단속하고 청정범행을 닦으며 [네 가지] 성스러운 진리를 보고 열반을 실현하는 것, 이것이 으뜸가는 행복이라네.
세상사에 부딪쳐 마음이 흔들리지 않고 슬픔 없고 티끌 없이 안온한 것, 이것이 으뜸가는 행복이라네.
이러한 것을 실천하면 어떤 곳에서건 패배하지 않고 모든 곳에서 안녕하리니, 이것이 그들에게 으뜸가는 행복이라네.`,
        get length() { return this.text.length; },
        estimatedTime: '12-18분',
        order: 2
    },

    // ========================================
    // 진언 (Mantras) - 3 new
    // ========================================
    omMani: {
        id: 'omMani',
        category: 'mantra',
        title: '육자대명왕진언',
        subtitle: '六字大明王眞言',
        description: '관세음보살의 대자대비를 상징하는 여섯 글자 진언',
        pattern: '옴 마니 반메 훔',
        repeat: 108,
        text: generateRepeatedText('옴 마니 반메 훔', 108),
        get length() { return this.text.length; },
        estimatedTime: '4-6분',
        order: 3
    },

    heartSutraMantra: {
        id: 'heartSutraMantra',
        category: 'mantra',
        title: '반야심경 진언',
        subtitle: '般若心經 眞言',
        description: '반야심경의 핵심 진언',
        text: '아제 아제 바라아제 바라승아제 모지 사바하',
        get length() { return this.text.length; },
        estimatedTime: '1분',
        order: 4
    },

    greatCompassion: {
        id: 'greatCompassion',
        category: 'mantra',
        title: '신묘장구대다라니',
        subtitle: '神妙章句大陀羅尼',
        description: '관세음보살의 큰 자비를 담은 신성한 진언',
        text: `나모라 다나다라야야 나막 알야 바로기제 쉬바라야 모지사다바야 마하사다바야 마하가로니가야
옴 살바 바예수 다라나 가라야 다사타 나막 알야 바로기제 쉬바라야
나막 노로기제 쉬바라야 마하보디사다바야 마하사다바야 마하가로니가야
옴 살바라바 예이수다라 나비갈얼데 훔 발라 나막 갈리다야
나막 알리야 바로기제 쉬바라야 다바태야
옴 아노가례 바라 사바하 시다야 사바하 마하시다야 사바하
시다유예실바라야 사바하 노라기제 사바하 비라기제 사바하
마하가리예 바라 발라 사바하 알라가례 발라 사바하
날라긴지 가라야 사바하 시다 살리남 사바하 모다나 사바하 마하모다나 사바하
가이라바예 사바하 가이라 내기바예 사바하 잔타 갈리 마하로사나 사바하 지기라 사바하
날리 날리 사바하 아리야 다라 사바하 바라제차 사바하 마라 날리 사바하`,
        get length() { return this.text.length; },
        estimatedTime: '8-12분',
        order: 5
    },

    // ========================================
    // 명호 (Buddha Names) - 2 new
    // ========================================
    namuAmitabul: {
        id: 'namuAmitabul',
        category: 'name',
        title: '나무아미타불',
        subtitle: '南無阿彌陀佛',
        description: '아미타불을 향한 귀의의 마음으로 108번 염송',
        pattern: '나무아미타불',
        repeat: 108,
        text: generateRepeatedText('나무아미타불', 108),
        get length() { return this.text.length; },
        estimatedTime: '4-6분',
        order: 6
    },

    namuSeokgamoni: {
        id: 'namuSeokgamoni',
        category: 'name',
        title: '나무석가모니불',
        subtitle: '南無釋迦牟尼佛',
        description: '석가모니 부처님께 108번의 귀의',
        pattern: '나무석가모니불',
        repeat: 108,
        text: generateRepeatedText('나무석가모니불', 108),
        get length() { return this.text.length; },
        estimatedTime: '5-7분',
        order: 7
    },

    // ========================================
    // 게송 (Verses) - 3 new
    // ========================================
    threeRefuges: {
        id: 'threeRefuges',
        category: 'verse',
        title: '삼귀의',
        subtitle: '三歸依',
        description: '불교 수행의 근본인 삼보에 대한 귀의',
        text: `부처님께 귀의합니다.
가르침에 귀의합니다.
승가에 귀의합니다.

부처님께 귀의하오니 원컨대 중생과 함께 큰 도를 깨달아 위없는 마음을 내게 하옵소서.
가르침에 귀의하오니 원컨대 중생과 함께 경장에 깊이 들어가 지혜가 바다와 같게 하옵소서.
승가에 귀의하오니 원컨대 중생과 함께 대중을 화합하여 일체가 장애 없게 하옵소서.`,
        get length() { return this.text.length; },
        estimatedTime: '2-3분',
        order: 8
    },

    fourVows: {
        id: 'fourVows',
        category: 'verse',
        title: '사홍서원',
        subtitle: '四弘誓願',
        description: '보살의 네 가지 큰 서원',
        text: `중생무변서원도
번뇌무진서원단
법문무량서원학
불도무상서원성`,
        get length() { return this.text.length; },
        estimatedTime: '1분',
        order: 9
    },

    impermanenceVerse: {
        id: 'impermanenceVerse',
        category: 'verse',
        title: '무상게',
        subtitle: '無常偈',
        description: '모든 현상의 무상함을 노래한 게송',
        text: `제행무상 시생멸법
생멸멸이 적멸위락

모든 지어진 것은 무상하니 나고 사라지는 법이로다.
남과 사라짐이 이미 사라지니 고요함이 바로 즐거움이로다.`,
        get length() { return this.text.length; },
        estimatedTime: '1-2분',
        order: 10
    },

    atishaHeart: {
        id: 'atishaHeart',
        category: 'verse',
        title: '해탈을 원하는 용감한 이의 가슴 속 여의주',
        subtitle: '아띠샤 스님',
        description: '해탈을 향한 수행자에게 주는 아띠샤 스님의 조언',
        text: `나모구루베 스승에게 절하옵니다.
앎이 수승하고 마음속 생각 매우 분명한 친구들에게, 스스로 경험이 없고 미천한 내가 조언을 해서는 아니 되오만.
심장보다 귀중한 친구 당신이 나에게 요청하였기에 어리석고 우매한 내가 친구의 마음에 이 조언을 바치노라.
친구들! 보리를 얻기 전까진 스승이 필요하기에 올바른 스승을 의지하라.
법의 의미를 깨닫기 전까지는 들음이 필요하기에 스승의 가르침을 들어라.
법은 이해 정도로 깨달을 수 없기에 이해만으로는 충분하지 않으니 이를 실천하라.
마음을 해치는 대상과 멀리하고 항상 공덕이 늘어나는 곳에 머물러라.
굳건함을 얻기 전까지는 모여 잡담 함이 해롭기에 오지의 숲 속에 의지하라.
번뇌가 생기게 하는 친구 버리고 공덕이 늘어나게 하는 친구 의지하는 그것에 마음을 두라.
언제나 하는 일이 마침이 없기에 놓아두고 편안하게 머물러라.
밤낮으로 늘 공덕을 회향하고 항상 본인 마음을 살피도록 하라.
구경에 있어 닦고 익힘 모두, 스승 의 말씀대로 행하라.
큰 공경으로 행한다면 머지않아 열매 속히 열리리라.
마음으로 법 다이 행한다면 먹는 것과 입는 것 두 가지 저절로 생기리라.
친구들! 욕망은 소금물 마시는 것과 같아 충족되지 않기에 만족할 줄 알라.
교만, 자만, 오만한 마음 모두 경책하여 순화시켜라.
복이라 부르는 온갖 것 그 또한 수행의 장애이기에 버려라.
얻음과 타인의 존경 마의 고삐이기에 골목의 돌처럼 치워라.
칭찬과 명예의 말들 속임이기에 콧물처럼 버려라.
지금의 건강, 행복, 가족, 이 세 가지 갖추더라도 잠깐이기에 뒤로 버려라.
이번 생보다 다음 생이 더욱 길기 에 다음 생의 양식 되는 재산들 자 원으로 감추어라.
모든 것 버리고 가야 하기에 그 무엇도 할 수 없나니 어디에도 집착하지 말라.
약한 자에게 연민심을 가지되 업신 여김과 핍박함을 버려라.
원수를 미워하고 친척을 좋아하면 화냄과 애착이 늘어나므로 차별을 없애라.
박식한 사람에게 질투하지 말고 공 경해서 그의 모든 면을 받아들여라.
남의 허물을 살피지 말고, 본인의 허물을 살펴서 본인의 허물을 썩은 피처럼 버려라.
자신의 공덕을 생각하지 말고 남의 공덕을 생각해서 모든 이의 하인인듯 여겨 공경하라.
모든 중생의 부모라는 생각을 가 져, 자식을 대하듯 자애심을 가져라.
항상 미소 짓는 얼굴과 자애심으로 화냄 없는 진실을 말하라.
쓸데없는 말이 많으면 잘못이 생기 기에 적당히 알맞게 말하라.
의미 없는 일이 많으면 선행이 작 아지므로 법답지 않은 일은 하지 말 라.
의미 없는 일에 정열을 쏟으면 고생만 할 뿐 가치가 없느니라.
모든 것들이 자기 욕심대로 되지 않으니, 남을 의지해서 성취해야 하기에 편안하게 놓으면 좋으리라.
여보게! 성현들이 우리를 좋아하지 않는다면 죽음과 다름이 없기에 흔들림 없이 정직하라.
이번 생의 행복과 고통은 과거의 업으로부터 비롯하기에 남에게 피해를 주지 말라.
모든 행복은 스승의 가피이기에 은헤에 보답하라.
본인의 마음이 순화되기 전까진 남의 마음을 순화시킬 수 없기에 먼저 본인 마음을 순화시켜라.
타심통 없이는 남을 제도 할 수 있는 능력이 없기에 수행 정진 하라.
모든 재산들을 놓고 가는 것이 확실하기에 재산 때문에 업을 짓지 말라.
물질적인 것에 방일하는 것은 의미가 없기에 보시의 가치를 알고 행하라.
이번 생과 다음 생이 아름다워지고 행복해지기에 항상 계율을 청정하게 지켜라.
오탁악세에는 화냄이 많아지기에 화냄이 없는 인욕의 갑옷을 입어라.
나태함의 힘으로 인해 아직도 윤회 세계에 남아있기에 수행 정진의 불을 키워라.
산란함의 길로써 인생을 마치기에 이제는 선정을 닦을 때 이니라.
사견의 힘으로는 공의 의미를 깨우 칠 수 없기에 완벽한 의미를 살펴 라.
친구들! 윤회의 진흙탕 여기에는 행복이 없으니 해탈의 마른 땅에 도달하라.
스승의 요의법을 자세히 닦고 윤회 고통의 강물을 말려라.
자신의 마음에 간직하고, 말로만 하는 것이 아닌 조언이기에 이를 잘 새겨라.
그렇게 한다면 나도 기쁘고 우리 모두 행복하리라.
무지한 나의 가르침이지만 당신은 부디 새겨들으소서.`,
        get length() { return this.text.length; },
        estimatedTime: '15-20분',
        order: 11
    }
};

/**
 * Validate sutra data integrity
 * Called automatically at module load
 */
function validateSutraData(data) {
    const errors = [];
    const seenOrders = new Set();

    for (const [key, sutra] of Object.entries(data)) {
        // Check required fields
        if (!sutra.id) errors.push(`${key}: missing id`);
        if (sutra.id !== key) errors.push(`${key}: id mismatch (id="${sutra.id}")`);
        if (!sutra.category) errors.push(`${key}: missing category`);
        if (!CATEGORIES[sutra.category]) errors.push(`${key}: invalid category "${sutra.category}"`);
        if (!sutra.title) errors.push(`${key}: missing title`);
        if (!sutra.text) errors.push(`${key}: missing text`);
        if (sutra.text && sutra.text.length === 0) errors.push(`${key}: empty text`);
        if (!sutra.description) errors.push(`${key}: missing description`);
        if (!sutra.estimatedTime) errors.push(`${key}: missing estimatedTime`);
        if (typeof sutra.order !== 'number') errors.push(`${key}: invalid order`);

        // Check order uniqueness
        if (seenOrders.has(sutra.order)) {
            errors.push(`${key}: duplicate order ${sutra.order}`);
        }
        seenOrders.add(sutra.order);

        // Validate length (using getter)
        const actualLength = sutra.text.length;
        const declaredLength = sutra.length;
        if (actualLength !== declaredLength) {
            errors.push(`${key}: length mismatch (declared ${declaredLength}, actual ${actualLength})`);
        }
    }

    if (errors.length > 0) {
        console.error('❌ Sutra data validation failed:', errors);
        throw new Error(`Invalid sutra data: ${errors.length} error(s)`);
    }

    console.log('✅ Sutra data validation passed - 11 sutras loaded');
}

// Validate on module load
validateSutraData(SUTRA_DATA);

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

// Backward compatibility alias
export const SUTRAS = SUTRA_DATA;
