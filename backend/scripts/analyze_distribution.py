#!/usr/bin/env python3
"""
Distribution Analyzer for Tripitaka Data Normalization

Analyzes source_summaries_ko.json to:
1. Report period/tradition value distributions
2. Identify unmapped values
3. Check writing style violations
4. Generate dry-run reports (JSON + Markdown)

Usage:
    python analyze_distribution.py [--output-dir reports]
"""

import json
import re
import argparse
from pathlib import Path
from datetime import datetime
from collections import Counter


class DistributionAnalyzer:
    def __init__(self, data_path: str, schema_dir: str):
        self.data_path = Path(data_path)
        self.schema_dir = Path(schema_dir)
        self.data = None
        self.tradition_map = None
        self.period_map = None
        self.style_rules = None

    def load_data(self):
        """Load source data and schema files."""
        with open(self.data_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        with open(self.schema_dir / 'tradition_map.json', 'r', encoding='utf-8') as f:
            self.tradition_map = json.load(f)

        with open(self.schema_dir / 'period_map.json', 'r', encoding='utf-8') as f:
            self.period_map = json.load(f)

        with open(self.schema_dir / 'style_rules.json', 'r', encoding='utf-8') as f:
            self.style_rules = json.load(f)

        print(f"Loaded {len(self.data['summaries'])} records from {self.data_path.name}")

    def normalize_tradition(self, raw_value: str) -> tuple[str, bool]:
        """
        Normalize tradition value using schema rules.
        Returns (normalized_value, is_mapped)
        """
        if not raw_value:
            return '미상', True

        value_lower = raw_value.lower().strip()
        value_lower = ' '.join(value_lower.split())

        for rule in self.tradition_map['pattern_rules']:
            for pattern in rule['patterns']:
                if pattern.lower() in value_lower:
                    return rule['target'], True

        # Fallback: contains '불교'
        if '불교' in value_lower:
            return '대승불교', True

        return '미상', False

    def normalize_period(self, raw_value: str) -> tuple[str, bool]:
        """
        Normalize period value using schema rules.
        Returns (normalized_value, is_mapped)
        """
        if not raw_value:
            return '미상', True

        # Check ambiguous mappings first (exact match)
        if raw_value in self.period_map.get('ambiguous_mappings', {}):
            return self.period_map['ambiguous_mappings'][raw_value], True

        value_lower = raw_value.lower().strip()

        for rule in self.period_map['pattern_rules']:
            # Check patterns
            for pattern in rule['patterns']:
                if pattern.lower() in value_lower:
                    return rule['target'], True
            # Check regex
            if 'regex' in rule:
                if re.search(rule['regex'], raw_value, re.IGNORECASE):
                    return rule['target'], True

        return '미상', False

    def check_style_violations(self, text: str) -> list[str]:
        """
        Check for forbidden writing style patterns.
        Returns list of found violations.
        """
        if not text:
            return []

        pattern = self.style_rules['forbidden_endings']['regex']
        matches = re.findall(pattern, text)
        return list(set(matches))

    def analyze(self) -> dict:
        """Run full analysis and return results."""
        results = {
            'timestamp': datetime.now().isoformat(),
            'total_records': len(self.data['summaries']),
            'tradition': {
                'raw_distribution': Counter(),
                'normalized_distribution': Counter(),
                'unmapped_values': [],
                'mapping_success_rate': 0.0
            },
            'period': {
                'raw_distribution': Counter(),
                'normalized_distribution': Counter(),
                'unmapped_values': [],
                'mapping_success_rate': 0.0
            },
            'style': {
                'total_violations': 0,
                'records_with_violations': 0,
                'violation_patterns': Counter(),
                'samples': []
            }
        }

        tradition_mapped = 0
        period_mapped = 0

        for record_id, record in self.data['summaries'].items():
            # Tradition analysis
            raw_tradition = record.get('tradition', '')
            results['tradition']['raw_distribution'][raw_tradition] += 1

            normalized_tradition, is_mapped = self.normalize_tradition(raw_tradition)
            results['tradition']['normalized_distribution'][normalized_tradition] += 1

            if is_mapped:
                tradition_mapped += 1
            else:
                results['tradition']['unmapped_values'].append({
                    'id': record_id,
                    'value': raw_tradition
                })

            # Period analysis
            raw_period = record.get('period', '')
            results['period']['raw_distribution'][raw_period] += 1

            normalized_period, is_mapped = self.normalize_period(raw_period)
            results['period']['normalized_distribution'][normalized_period] += 1

            if is_mapped:
                period_mapped += 1
            else:
                results['period']['unmapped_values'].append({
                    'id': record_id,
                    'value': raw_period
                })

            # Style analysis
            brief_summary = record.get('brief_summary', '')
            violations = self.check_style_violations(brief_summary)

            if violations:
                results['style']['records_with_violations'] += 1
                results['style']['total_violations'] += len(violations)

                for v in violations:
                    results['style']['violation_patterns'][v] += 1

                if len(results['style']['samples']) < 20:
                    results['style']['samples'].append({
                        'id': record_id,
                        'violations': violations,
                        'text': brief_summary[:200] + '...' if len(brief_summary) > 200 else brief_summary
                    })

        # Calculate success rates
        total = results['total_records']
        results['tradition']['mapping_success_rate'] = round(tradition_mapped / total * 100, 2) if total > 0 else 0
        results['period']['mapping_success_rate'] = round(period_mapped / total * 100, 2) if total > 0 else 0

        # Convert Counters to sorted dicts for JSON serialization
        results['tradition']['raw_distribution'] = dict(
            sorted(results['tradition']['raw_distribution'].items(), key=lambda x: -x[1])
        )
        results['tradition']['normalized_distribution'] = dict(
            sorted(results['tradition']['normalized_distribution'].items(), key=lambda x: -x[1])
        )
        results['period']['raw_distribution'] = dict(
            sorted(results['period']['raw_distribution'].items(), key=lambda x: -x[1])
        )
        results['period']['normalized_distribution'] = dict(
            sorted(results['period']['normalized_distribution'].items(), key=lambda x: -x[1])
        )
        results['style']['violation_patterns'] = dict(
            sorted(results['style']['violation_patterns'].items(), key=lambda x: -x[1])
        )

        return results

    def generate_markdown_report(self, results: dict) -> str:
        """Generate human-readable Markdown report."""
        lines = [
            "# Tripitaka Data Normalization Analysis Report",
            "",
            f"**Generated:** {results['timestamp']}",
            f"**Total Records:** {results['total_records']:,}",
            "",
            "---",
            "",
            "## 1. Tradition (종파) Analysis",
            "",
            f"### Mapping Success Rate: {results['tradition']['mapping_success_rate']}%",
            "",
            "### Normalized Distribution (12 Categories)",
            "",
            "| Category | Count | Percentage |",
            "|----------|-------|------------|",
        ]

        total = results['total_records']
        for cat, count in results['tradition']['normalized_distribution'].items():
            pct = round(count / total * 100, 1) if total > 0 else 0
            lines.append(f"| {cat} | {count:,} | {pct}% |")

        lines.extend([
            "",
            f"### Unmapped Values: {len(results['tradition']['unmapped_values'])}",
            "",
        ])

        if results['tradition']['unmapped_values']:
            lines.append("| ID | Raw Value |")
            lines.append("|-----|-----------|")
            for item in results['tradition']['unmapped_values'][:20]:
                lines.append(f"| {item['id']} | {item['value']} |")
            if len(results['tradition']['unmapped_values']) > 20:
                lines.append(f"| ... | ({len(results['tradition']['unmapped_values']) - 20} more) |")

        lines.extend([
            "",
            "---",
            "",
            "## 2. Period (시대) Analysis",
            "",
            f"### Mapping Success Rate: {results['period']['mapping_success_rate']}%",
            "",
            "### Normalized Distribution (14 Categories + Fallback)",
            "",
            "| Category | Count | Percentage |",
            "|----------|-------|------------|",
        ])

        for cat, count in results['period']['normalized_distribution'].items():
            pct = round(count / total * 100, 1) if total > 0 else 0
            lines.append(f"| {cat} | {count:,} | {pct}% |")

        lines.extend([
            "",
            f"### Unmapped Values: {len(results['period']['unmapped_values'])}",
            "",
        ])

        if results['period']['unmapped_values']:
            lines.append("| ID | Raw Value |")
            lines.append("|-----|-----------|")
            for item in results['period']['unmapped_values'][:20]:
                lines.append(f"| {item['id']} | {item['value']} |")
            if len(results['period']['unmapped_values']) > 20:
                lines.append(f"| ... | ({len(results['period']['unmapped_values']) - 20} more) |")

        lines.extend([
            "",
            "---",
            "",
            "## 3. Writing Style (문체) Analysis",
            "",
            f"### Records with Violations: {results['style']['records_with_violations']} / {total}",
            f"### Total Violations: {results['style']['total_violations']}",
            "",
            "### Violation Pattern Distribution",
            "",
            "| Pattern | Count |",
            "|---------|-------|",
        ])

        for pattern, count in results['style']['violation_patterns'].items():
            lines.append(f"| `{pattern}` | {count} |")

        lines.extend([
            "",
            "### Sample Violations (First 20)",
            "",
        ])

        for sample in results['style']['samples']:
            lines.extend([
                f"**{sample['id']}** - Patterns: `{', '.join(sample['violations'])}`",
                f"> {sample['text']}",
                "",
            ])

        lines.extend([
            "",
            "---",
            "",
            "## 4. Recommendations",
            "",
            "### Priority Actions:",
            "",
        ])

        # Generate recommendations
        if results['period']['mapping_success_rate'] < 100:
            unmapped_count = len(results['period']['unmapped_values'])
            lines.append(f"1. **Period Mapping**: {unmapped_count} unmapped period values need review")

        if results['tradition']['mapping_success_rate'] < 100:
            unmapped_count = len(results['tradition']['unmapped_values'])
            lines.append(f"2. **Tradition Mapping**: {unmapped_count} unmapped tradition values need review")

        if results['style']['records_with_violations'] > 0:
            lines.append(f"3. **Style Normalization**: {results['style']['records_with_violations']} records need 한다/이다체 conversion")

        lines.extend([
            "",
            "---",
            "",
            "*Report generated by analyze_distribution.py*",
        ])

        return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Analyze Tripitaka data distribution')
    parser.add_argument('--data', default='source_explorer/source_data/source_summaries_ko.json',
                        help='Path to source data JSON')
    parser.add_argument('--schema-dir', default='schema',
                        help='Path to schema directory')
    parser.add_argument('--output-dir', default='reports',
                        help='Output directory for reports')
    args = parser.parse_args()

    # Resolve paths relative to script location
    script_dir = Path(__file__).parent
    data_path = script_dir / args.data
    schema_dir = script_dir / args.schema_dir
    output_dir = script_dir / args.output_dir

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run analysis
    analyzer = DistributionAnalyzer(data_path, schema_dir)
    analyzer.load_data()
    results = analyzer.analyze()

    # Save JSON report
    json_path = output_dir / 'distribution_analysis.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"JSON report saved to: {json_path}")

    # Save Markdown report
    md_report = analyzer.generate_markdown_report(results)
    md_path = output_dir / 'distribution_analysis.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_report)
    print(f"Markdown report saved to: {md_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"Total Records: {results['total_records']:,}")
    print(f"\nTradition Mapping: {results['tradition']['mapping_success_rate']}%")
    print(f"  - Unmapped: {len(results['tradition']['unmapped_values'])}")
    print(f"\nPeriod Mapping: {results['period']['mapping_success_rate']}%")
    print(f"  - Unmapped: {len(results['period']['unmapped_values'])}")
    print(f"\nStyle Violations: {results['style']['records_with_violations']} records")
    print("=" * 60)


if __name__ == '__main__':
    main()
