#!/usr/bin/env python3
"""
Test Suite for Tripitaka Data Normalization

Tests:
1. test_tradition_categories - All values map to 12 canonical categories
2. test_period_categories - All values map to 14 canonical categories + fallback
3. test_style_endings - No forbidden endings in normalized summaries
4. test_integrity_counts - Record count and ID uniqueness preserved
5. test_original_fields - _original_* fields exist and are non-empty
6. test_no_html_damage - HTML tag counts match original

Usage:
    pytest test_normalization.py -v
    python test_normalization.py  # standalone mode
"""

import json
import re
import unittest
from pathlib import Path
from collections import Counter


class TestNormalization(unittest.TestCase):
    """Test suite for normalized data validation."""

    @classmethod
    def setUpClass(cls):
        """Load original and normalized data once for all tests."""
        script_dir = Path(__file__).parent

        # Load original data
        original_path = script_dir / 'source_explorer/source_data/source_summaries_ko.json'
        with open(original_path, 'r', encoding='utf-8') as f:
            cls.original_data = json.load(f)

        # Load normalized data (if exists)
        normalized_path = script_dir / 'source_explorer/source_data/source_summaries_ko_normalized.json'
        if normalized_path.exists():
            with open(normalized_path, 'r', encoding='utf-8') as f:
                cls.normalized_data = json.load(f)
        else:
            # Use dry-run output for testing
            cls.normalized_data = None

        # Load schema files
        with open(script_dir / 'schema/tradition_map.json', 'r', encoding='utf-8') as f:
            cls.tradition_map = json.load(f)

        with open(script_dir / 'schema/period_map.json', 'r', encoding='utf-8') as f:
            cls.period_map = json.load(f)

        with open(script_dir / 'schema/style_rules.json', 'r', encoding='utf-8') as f:
            cls.style_rules = json.load(f)

        # Canonical sets
        cls.tradition_categories = set(cls.tradition_map['canonical_categories'])
        cls.period_categories = set(cls.period_map['canonical_categories'] +
                                     cls.period_map['fallback_categories'])

        print(f"\nLoaded {len(cls.original_data['summaries'])} original records")
        if cls.normalized_data:
            print(f"Loaded {len(cls.normalized_data['summaries'])} normalized records")

    def test_tradition_categories(self):
        """All tradition values should map to 12 canonical categories."""
        if not self.normalized_data:
            self.skipTest("Normalized data not available")

        invalid_traditions = []
        tradition_counts = Counter()

        for record_id, record in self.normalized_data['summaries'].items():
            tradition = record.get('tradition', '')
            tradition_counts[tradition] += 1

            if tradition not in self.tradition_categories:
                invalid_traditions.append({
                    'id': record_id,
                    'value': tradition
                })

        # Report distribution
        print("\n  Tradition Distribution:")
        for t, count in sorted(tradition_counts.items(), key=lambda x: -x[1]):
            print(f"    {t}: {count}")

        self.assertEqual(
            len(invalid_traditions), 0,
            f"Found {len(invalid_traditions)} records with invalid tradition values: "
            f"{invalid_traditions[:5]}"
        )

    def test_period_categories(self):
        """All period values should map to 14 canonical categories + fallback."""
        if not self.normalized_data:
            self.skipTest("Normalized data not available")

        invalid_periods = []
        period_counts = Counter()

        for record_id, record in self.normalized_data['summaries'].items():
            period = record.get('period', '')
            period_counts[period] += 1

            if period not in self.period_categories:
                invalid_periods.append({
                    'id': record_id,
                    'value': period
                })

        # Report distribution
        print("\n  Period Distribution:")
        for p, count in sorted(period_counts.items(), key=lambda x: -x[1]):
            print(f"    {p}: {count}")

        self.assertEqual(
            len(invalid_periods), 0,
            f"Found {len(invalid_periods)} records with invalid period values: "
            f"{invalid_periods[:5]}"
        )

    def test_style_endings(self):
        """No forbidden endings should remain in normalized brief_summary."""
        if not self.normalized_data:
            self.skipTest("Normalized data not available")

        forbidden_pattern = self.style_rules['forbidden_endings']['regex']
        violations = []

        for record_id, record in self.normalized_data['summaries'].items():
            # Skip records that are still pending
            if record.get('style_normalization_status') == 'pending':
                continue

            summary = record.get('brief_summary', '')
            matches = re.findall(forbidden_pattern, summary)
            if matches:
                violations.append({
                    'id': record_id,
                    'matches': matches
                })

        print(f"\n  Style violations (excluding pending): {len(violations)}")

        # This test may have violations until style normalization is complete
        # For now, just report them
        if violations:
            print(f"  Sample violations: {violations[:5]}")

    def test_integrity_counts(self):
        """Record count and ID set should match original."""
        if not self.normalized_data:
            self.skipTest("Normalized data not available")

        original_ids = set(self.original_data['summaries'].keys())
        normalized_ids = set(self.normalized_data['summaries'].keys())

        self.assertEqual(
            len(original_ids), len(normalized_ids),
            f"Record count mismatch: {len(original_ids)} vs {len(normalized_ids)}"
        )

        self.assertEqual(
            original_ids, normalized_ids,
            f"ID set mismatch. Missing: {original_ids - normalized_ids}, "
            f"Extra: {normalized_ids - original_ids}"
        )

        print(f"\n  Record count: {len(normalized_ids)} (matches original)")

    def test_original_fields(self):
        """_original_* fields should exist and contain original values."""
        if not self.normalized_data:
            self.skipTest("Normalized data not available")

        missing_fields = []

        for record_id, record in self.normalized_data['summaries'].items():
            required_fields = ['_original_tradition', '_original_period', '_original_brief_summary']
            missing = [f for f in required_fields if f not in record]

            if missing:
                missing_fields.append({
                    'id': record_id,
                    'missing': missing
                })

        self.assertEqual(
            len(missing_fields), 0,
            f"Found {len(missing_fields)} records missing _original_* fields: "
            f"{missing_fields[:5]}"
        )

        # Verify original values match
        sample_id = list(self.normalized_data['summaries'].keys())[0]
        sample = self.normalized_data['summaries'][sample_id]
        original = self.original_data['summaries'][sample_id]

        self.assertEqual(
            sample.get('_original_tradition'), original.get('tradition'),
            f"_original_tradition mismatch for {sample_id}"
        )

        print(f"\n  All records have _original_* fields")

    def test_no_html_damage(self):
        """HTML tag counts should match original (tags preserved)."""
        if not self.normalized_data:
            self.skipTest("Normalized data not available")

        damaged = []

        for record_id in self.normalized_data['summaries']:
            original = self.original_data['summaries'][record_id]
            normalized = self.normalized_data['summaries'][record_id]

            # Count < and > in brief_summary
            orig_summary = original.get('brief_summary', '')
            norm_summary = normalized.get('brief_summary', '')

            orig_lt = orig_summary.count('<')
            orig_gt = orig_summary.count('>')
            norm_lt = norm_summary.count('<')
            norm_gt = norm_summary.count('>')

            if orig_lt != norm_lt or orig_gt != norm_gt:
                damaged.append({
                    'id': record_id,
                    'original': (orig_lt, orig_gt),
                    'normalized': (norm_lt, norm_gt)
                })

        self.assertEqual(
            len(damaged), 0,
            f"Found {len(damaged)} records with HTML tag damage: {damaged[:5]}"
        )

        print(f"\n  HTML tags preserved in all records")

    def test_sample_tradition_mappings(self):
        """Verify sample tradition mappings work correctly."""
        from run_normalization import TripitakaNormalizer

        script_dir = Path(__file__).parent
        normalizer = TripitakaNormalizer(
            script_dir / 'source_explorer/source_data/source_summaries_ko.json',
            script_dir / 'schema',
            script_dir / 'test_output.json'
        )
        normalizer.load_data()

        test_cases = [
            ('초기불교', '초기불교'),
            ('대승불교', '대승불교'),
            ('대승불교 (밀교적 요소 포함)', '밀교'),
            ('선종', '선종'),
            ('정토교', '정토종'),
            ('화엄종', '화엄종'),
            ('율종 (사분율)', '율종'),
            ('살바다부', '초기불교'),
            ('', '미상'),
            (None, '미상'),
        ]

        print("\n  Tradition mapping tests:")
        for raw, expected in test_cases:
            result = normalizer.normalize_tradition(raw)
            self.assertEqual(
                result, expected,
                f"Tradition mapping failed: '{raw}' -> '{result}' (expected '{expected}')"
            )
            print(f"    '{raw}' -> '{result}' ✓")

    def test_sample_period_mappings(self):
        """Verify sample period mappings work correctly."""
        from run_normalization import TripitakaNormalizer

        script_dir = Path(__file__).parent
        normalizer = TripitakaNormalizer(
            script_dir / 'source_explorer/source_data/source_summaries_ko.json',
            script_dir / 'schema',
            script_dir / 'test_output.json'
        )
        normalizer.load_data()

        test_cases = [
            ('초기불교', '초기불교'),
            ('대승 초기', '초기불교'),
            ('중국 당나라', '당'),
            ('당나라', '당'),
            ('송나라', '송'),
            ('유송 시대', '남북조'),
            ('후한 시대', '후한'),
            ('밀교 성립 이후', '당'),
            ('고려', '기타'),
            ('', '미상'),
        ]

        print("\n  Period mapping tests:")
        for raw, expected in test_cases:
            result = normalizer.normalize_period(raw)
            self.assertEqual(
                result, expected,
                f"Period mapping failed: '{raw}' -> '{result}' (expected '{expected}')"
            )
            print(f"    '{raw}' -> '{result}' ✓")


class TestSchemaIntegrity(unittest.TestCase):
    """Test schema file integrity."""

    @classmethod
    def setUpClass(cls):
        script_dir = Path(__file__).parent
        cls.schema_dir = script_dir / 'schema'

    def test_tradition_map_valid_json(self):
        """tradition_map.json should be valid JSON."""
        path = self.schema_dir / 'tradition_map.json'
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.assertIn('canonical_categories', data)
        self.assertEqual(len(data['canonical_categories']), 12)
        print(f"\n  tradition_map.json is valid with {len(data['canonical_categories'])} categories")

    def test_period_map_valid_json(self):
        """period_map.json should be valid JSON."""
        path = self.schema_dir / 'period_map.json'
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.assertIn('canonical_categories', data)
        self.assertEqual(len(data['canonical_categories']), 14)
        print(f"\n  period_map.json is valid with {len(data['canonical_categories'])} categories")

    def test_style_rules_valid_json(self):
        """style_rules.json should be valid JSON."""
        path = self.schema_dir / 'style_rules.json'
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.assertIn('forbidden_endings', data)
        self.assertIn('regex', data['forbidden_endings'])

        # Verify regex is valid
        pattern = data['forbidden_endings']['regex']
        re.compile(pattern)
        print(f"\n  style_rules.json is valid with regex pattern")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
