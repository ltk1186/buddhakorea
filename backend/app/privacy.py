"""
PII Protection for Buddha Korea RAG System

Lightweight regex-based PII masking with Korean language support.
No heavy ML dependencies - pure Python stdlib for production reliability.
"""

import re
from typing import Dict, Pattern

# Korean-specific PII patterns
KOREAN_PII_PATTERNS: Dict[str, Pattern] = {
    "korean_rrn": re.compile(r'(?<![0-9])\d{6}-?\d{7}(?![0-9])'),  # 주민등록번호
    "korean_phone": re.compile(r'(?<![0-9])01[0-9][-\s]?[0-9]{3,4}[-\s]?[0-9]{4}(?![0-9])'),  # 휴대폰
    "email": re.compile(r'(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}(?![A-Za-z0-9])'),
    "ip_address": re.compile(r'(?<![0-9.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9.])'),
}


def mask_pii(text: str) -> str:
    """
    Mask PII in text before logging.

    Performance: <5ms per query (acceptable overhead).

    Args:
        text: Input text potentially containing PII

    Returns:
        Text with PII masked

    Examples:
        >>> mask_pii("이메일: user@test.com")
        '이메일: [EMAIL_MASKED]'
        >>> mask_pii("전화: 010-1234-5678")
        '전화: [KOREAN_PHONE_MASKED]'
    """
    masked = text

    # Apply all patterns
    for pii_type, pattern in KOREAN_PII_PATTERNS.items():
        masked = pattern.sub(f"[{pii_type.upper()}_MASKED]", masked)

    return masked


def anonymize_ip(ip: str) -> str:
    """
    Anonymize IP address by zeroing last octet.

    Args:
        ip: IP address string

    Returns:
        Anonymized IP

    Examples:
        >>> anonymize_ip("192.168.1.100")
        '192.168.1.0'
    """
    parts = ip.split(".")
    return f"{parts[0]}.{parts[1]}.{parts[2]}.0" if len(parts) == 4 else ip


# Unit tests (run with: python privacy.py)
def test_pii_masking():
    """Comprehensive PII test suite for Korean data."""
    test_cases = [
        # (input_text, sensitive_data, should_be_present_after_masking)
        ("이메일 user@test.com 입니다", "user@test.com", False),
        ("010-1234-5678로 전화주세요", "010-1234-5678", False),
        ("IP는 192.168.1.100", "192.168.1.100", False),
        ("주민등록번호 901225-1234567", "901225-1234567", False),
        ("안녕하세요", "안녕하세요", True),  # No PII
        ("Multiple: user@ex.com and 010-9876-5432", "user@ex.com", False),
        ("Multiple: user@ex.com and 010-9876-5432", "010-9876-5432", False),
    ]

    failures = []
    for i, (text, sensitive, should_remain) in enumerate(test_cases):
        masked = mask_pii(text)
        if should_remain:
            if sensitive not in masked:
                failures.append(f"Test {i+1} FAILED: Over-masked non-PII\n  Input: {text}\n  Output: {masked}")
        else:
            if sensitive in masked:
                failures.append(f"Test {i+1} FAILED: Did not mask PII\n  Input: {text}\n  Output: {masked}\n  Expected to mask: {sensitive}")

    # IP anonymization tests
    ip_tests = [
        ("192.168.1.100", "192.168.1.0"),
        ("10.0.0.255", "10.0.0.0"),
        ("invalid", "invalid"),
    ]

    for ip_in, ip_expected in ip_tests:
        result = anonymize_ip(ip_in)
        if result != ip_expected:
            failures.append(f"IP anonymization FAILED: {ip_in} -> {result} (expected {ip_expected})")

    if failures:
        print("❌ PII Masking Tests FAILED:")
        for failure in failures:
            print(failure)
        return False
    else:
        print("✅ All PII masking tests passed (Korean language support verified)")
        return True


if __name__ == "__main__":
    import sys
    success = test_pii_masking()
    sys.exit(0 if success else 1)
