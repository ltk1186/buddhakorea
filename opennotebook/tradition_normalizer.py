"""
Tradition Normalizer for Buddhist Scripture Data

Normalizes 173+ varied tradition values into 12 canonical categories.
This improves filter reliability and user experience.
"""

from typing import Optional

# Canonical tradition categories with Korean and English names
CANONICAL_TRADITIONS = {
    '초기불교': 'Early Buddhism',
    '대승불교': 'Mahayana Buddhism',
    '밀교': 'Esoteric Buddhism (Tantra)',
    '선종': 'Zen Buddhism (Chan)',
    '천태종': 'Tiantai School',
    '화엄종': 'Huayan School',
    '정토종': 'Pure Land Buddhism',
    '유식불교': 'Yogacara (Consciousness-Only)',
    '율종': 'Vinaya School',
    '삼론종': 'Sanlun (Madhyamaka)',
    '기타': 'Other',
    '미상': 'Unknown'
}

# Mapping rules: keyword patterns to canonical traditions
# Order matters - more specific patterns should come first
TRADITION_PATTERNS = [
    # 초기불교 (Early Buddhism)
    (['초기불교', '초기 불교', '부파불교', '소승불교', '근본설일체유부',
      '설일체유부', '아비달마', '상좌부', '남방불교', '테라바다',
      '아함', '니까야', '성문승', '독각승'], '초기불교'),

    # 밀교 (Esoteric Buddhism) - check before 대승불교
    (['밀교', '탄트라', '진언종', '진언', '다라니', '만트라',
      '금강승', '비밀불교'], '밀교'),

    # 선종 (Zen/Chan) - includes 선불교 as common alternative name
    (['선종', '선불교', '선 불교', '참선', '조동종', '임제종', '위앙종',
      '법안종', '운문종', '황벽', '달마', '육조'], '선종'),

    # 천태종 (Tiantai)
    (['천태종', '천태', '법화종', '법화'], '천태종'),

    # 화엄종 (Huayan)
    (['화엄종', '화엄', '현수종', '법계'], '화엄종'),

    # 정토종 (Pure Land)
    (['정토종', '정토', '정토교', '염불', '아미타', '극락',
      '무량수', '관경'], '정토종'),

    # 유식불교 (Yogacara)
    (['유식', '법상종', '법상', '유가', '식학', '유식학'], '유식불교'),

    # 율종 (Vinaya)
    (['율종', '율장', '계율', '사분율', '오분율', '십송율',
      '비구율', '비구니율', '승가'], '율종'),

    # 삼론종 (Sanlun/Madhyamaka)
    (['삼론종', '삼론', '중관', '공종', '지론종'], '삼론종'),

    # 대승불교 (Mahayana) - generic fallback for 대승
    (['대승불교', '대승', '보살승', 'mahayana', '대승 초기'], '대승불교'),

    # 기타 (Other)
    (['경교', '마니교', '네스토리우스', '중국 불교', '티베트', '일본불교'], '기타'),
]


def normalize_tradition(raw_tradition: Optional[str]) -> str:
    """
    Normalize a raw tradition value to a canonical category.

    Args:
        raw_tradition: The raw tradition string from the data

    Returns:
        A canonical tradition category string
    """
    if not raw_tradition:
        return '미상'

    # Clean the input
    tradition_lower = raw_tradition.lower().strip()

    # Remove newlines and extra whitespace
    tradition_lower = ' '.join(tradition_lower.split())

    # Check each pattern group
    for patterns, canonical in TRADITION_PATTERNS:
        for pattern in patterns:
            if pattern.lower() in tradition_lower:
                return canonical

    # If no pattern matches but has "불교" in it, default to 대승불교
    if '불교' in tradition_lower:
        return '대승불교'

    return '미상'


def get_normalized_traditions() -> list:
    """
    Get list of all canonical tradition categories for filter UI.

    Returns:
        List of canonical tradition names in display order
    """
    return [
        '초기불교',
        '대승불교',
        '밀교',
        '선종',
        '천태종',
        '화엄종',
        '정토종',
        '유식불교',
        '율종',
        '삼론종',
        '기타',
        '미상'
    ]


def get_tradition_info(canonical: str) -> dict:
    """
    Get detailed information about a canonical tradition.

    Args:
        canonical: Canonical tradition name

    Returns:
        Dict with english name and description
    """
    info = {
        '초기불교': {
            'english': 'Early Buddhism',
            'description': '부처님 재세시와 그 이후 부파불교 시대의 가르침'
        },
        '대승불교': {
            'english': 'Mahayana Buddhism',
            'description': '보살도를 강조하는 대승 불교 전통'
        },
        '밀교': {
            'english': 'Esoteric Buddhism',
            'description': '진언과 다라니를 중시하는 밀교 전통'
        },
        '선종': {
            'english': 'Zen Buddhism',
            'description': '참선과 깨달음을 강조하는 선 전통'
        },
        '천태종': {
            'english': 'Tiantai School',
            'description': '법화경을 근본으로 하는 천태 전통'
        },
        '화엄종': {
            'english': 'Huayan School',
            'description': '화엄경을 근본으로 하는 화엄 전통'
        },
        '정토종': {
            'english': 'Pure Land Buddhism',
            'description': '아미타불 정토 왕생을 염원하는 전통'
        },
        '유식불교': {
            'english': 'Yogacara',
            'description': '유식학을 기반으로 하는 법상종 전통'
        },
        '율종': {
            'english': 'Vinaya School',
            'description': '계율을 중시하는 율장 전통'
        },
        '삼론종': {
            'english': 'Sanlun School',
            'description': '중관 사상을 기반으로 하는 삼론 전통'
        },
        '기타': {
            'english': 'Other',
            'description': '기타 종교 또는 특수 전통'
        },
        '미상': {
            'english': 'Unknown',
            'description': '전통이 명확하지 않은 경우'
        }
    }
    return info.get(canonical, {'english': 'Unknown', 'description': ''})


# Test function
if __name__ == '__main__':
    test_cases = [
        '초기불교',
        '대승불교',
        '대승불교 (밀교적 요소 포함)',
        '대승불교 (법상종)',
        '선종',
        '대승불교 (천태종)',
        '밀교',
        '대승불교, 밀교',
        '정토교',
        '화엄종',
        '율종 (사분율)',
        None,
        '',
        '경교 (네스토리우스파 기독교)',
    ]

    print("Tradition Normalization Test Results:")
    print("-" * 50)
    for raw in test_cases:
        normalized = normalize_tradition(raw)
        print(f"'{raw}' -> '{normalized}'")
