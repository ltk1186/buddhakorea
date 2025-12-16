#!/usr/bin/env python3
"""
Tripitaka Data Normalization Script

Normalizes source_summaries_ko.json:
1. Tradition → 12 canonical categories
2. Period → 14 canonical categories + fallback
3. Writing style → 한다/이다체

Usage:
    python run_normalization.py [--dry-run] [--skip-style]

Options:
    --dry-run      Generate diff report without modifying files
    --skip-style   Skip API-based style normalization
    --output       Output file path (default: source_summaries_ko_normalized.json)
"""

import json
import re
import argparse
import os
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

# Optional imports for style normalization
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel
    from dotenv import load_dotenv
    GENAI_AVAILABLE = True
except ImportError:
    try:
        import google.generativeai as genai
        from dotenv import load_dotenv
        GENAI_AVAILABLE = True
        vertexai = None
    except ImportError:
        GENAI_AVAILABLE = False
        vertexai = None
        genai = None


class TripitakaNormalizer:
    def __init__(self, data_path: str, schema_dir: str, output_path: str):
        self.data_path = Path(data_path)
        self.schema_dir = Path(schema_dir)
        self.output_path = Path(output_path)
        self.data = None
        self.tradition_map = None
        self.period_map = None
        self.style_rules = None
        self.stats = {
            'total': 0,
            'tradition_changed': 0,
            'period_changed': 0,
            'style_changed': 0,
            'style_pending': 0,
            'detailed_style_changed': 0,
            'detailed_style_pending': 0,
            'errors': []
        }

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

        self.stats['total'] = len(self.data['summaries'])
        print(f"Loaded {self.stats['total']} records from {self.data_path.name}")

    def backup_data(self):
        """Create timestamped backup of original data."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.data_path.parent / f"source_summaries_ko.backup_{timestamp}.json"
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        print(f"Backup created: {backup_path}")
        return backup_path

    def normalize_tradition(self, raw_value: str) -> str:
        """Normalize tradition value using schema rules."""
        if not raw_value:
            return '미상'

        value_lower = raw_value.lower().strip()
        value_lower = ' '.join(value_lower.split())

        for rule in self.tradition_map['pattern_rules']:
            for pattern in rule['patterns']:
                if pattern.lower() in value_lower:
                    return rule['target']

        # Fallback: contains '불교'
        if '불교' in value_lower:
            return '대승불교'

        return '미상'

    def normalize_period(self, raw_value: str) -> str:
        """Normalize period value using schema rules."""
        if not raw_value:
            return '미상'

        # Check ambiguous mappings first (exact match)
        if raw_value in self.period_map.get('ambiguous_mappings', {}):
            return self.period_map['ambiguous_mappings'][raw_value]

        value_lower = raw_value.lower().strip()

        for rule in self.period_map['pattern_rules']:
            # Check patterns
            for pattern in rule['patterns']:
                if pattern.lower() in value_lower:
                    return rule['target']
            # Check regex
            if 'regex' in rule:
                if re.search(rule['regex'], raw_value, re.IGNORECASE):
                    return rule['target']

        # Fallback rules
        if '밀교' in raw_value:
            return '당'

        return '미상'

    def has_style_violations(self, text: str) -> bool:
        """Check if text has forbidden writing style patterns."""
        if not text:
            return False
        pattern = self.style_rules['forbidden_endings']['regex']
        return bool(re.search(pattern, text))

    def normalize_style_with_api(self, text: str, record_id: str) -> tuple[str, bool]:
        """
        Use Gemini API to convert writing style.
        Returns (converted_text, success)
        """
        try:
            prompt = self.style_rules['api_config']['prompt_template'].format(text=text)

            # Rate limiting: wait 0.5 second between API calls
            time.sleep(0.5)

            # Use Vertex AI or google.generativeai
            if vertexai and hasattr(self, '_vertex_model'):
                response = self._vertex_model.generate_content(prompt)
            elif genai:
                model = genai.GenerativeModel(self.style_rules['api_config']['model'])
                response = model.generate_content(prompt)
            else:
                return text, False

            if response.text:
                converted = response.text.strip()
                # Basic sanity check: result should be similar length
                if 0.5 < len(converted) / len(text) < 2.0:
                    return converted, True
                else:
                    self.stats['errors'].append({
                        'id': record_id,
                        'type': 'style_length_mismatch',
                        'original_len': len(text),
                        'result_len': len(converted)
                    })
                    return text, False
            return text, False
        except Exception as e:
            self.stats['errors'].append({
                'id': record_id,
                'type': 'style_api_error',
                'error': str(e)
            })
            return text, False

    def normalize_record(self, record_id: str, record: dict, skip_style: bool = False) -> dict:
        """Normalize a single record."""
        normalized = record.copy()

        # Save original values
        normalized['_original_tradition'] = record.get('tradition', '')
        normalized['_original_period'] = record.get('period', '')
        normalized['_original_brief_summary'] = record.get('brief_summary', '')
        normalized['_original_detailed_summary'] = record.get('detailed_summary', '')

        # Normalize tradition
        original_tradition = record.get('tradition', '')
        new_tradition = self.normalize_tradition(original_tradition)
        if new_tradition != original_tradition:
            normalized['tradition'] = new_tradition
            self.stats['tradition_changed'] += 1

        # Normalize period
        original_period = record.get('period', '')
        new_period = self.normalize_period(original_period)
        if new_period != original_period:
            normalized['period'] = new_period
            self.stats['period_changed'] += 1

        # Normalize style (if not skipped)
        if not skip_style:
            # Normalize brief_summary
            brief_summary = record.get('brief_summary', '')
            if self.has_style_violations(brief_summary):
                new_summary, success = self.normalize_style_with_api(brief_summary, record_id)
                if success:
                    normalized['brief_summary'] = new_summary
                    normalized['style_normalization_status'] = 'completed'
                    self.stats['style_changed'] += 1
                else:
                    normalized['style_normalization_status'] = 'pending'
                    self.stats['style_pending'] += 1

            # Normalize detailed_summary
            detailed_summary = record.get('detailed_summary', '')
            if self.has_style_violations(detailed_summary):
                new_detailed, success = self.normalize_style_with_api(detailed_summary, record_id + '_detailed')
                if success:
                    normalized['detailed_summary'] = new_detailed
                    normalized['detailed_style_normalization_status'] = 'completed'
                    self.stats['detailed_style_changed'] += 1
                else:
                    normalized['detailed_style_normalization_status'] = 'pending'
                    self.stats['detailed_style_pending'] += 1
        else:
            # Mark records that need style normalization
            brief_summary = record.get('brief_summary', '')
            if self.has_style_violations(brief_summary):
                normalized['style_normalization_status'] = 'pending'
                self.stats['style_pending'] += 1

            detailed_summary = record.get('detailed_summary', '')
            if self.has_style_violations(detailed_summary):
                normalized['detailed_style_normalization_status'] = 'pending'
                self.stats['detailed_style_pending'] += 1

        return normalized

    def run(self, dry_run: bool = False, skip_style: bool = False):
        """Run full normalization."""
        print(f"\nStarting normalization (dry_run={dry_run}, skip_style={skip_style})...")

        if not dry_run:
            self.backup_data()

        # Initialize Gemini API if style normalization is enabled
        if not skip_style:
            if not GENAI_AVAILABLE:
                print("Warning: Gemini SDK not installed. Skipping style normalization.")
                skip_style = True
            else:
                load_dotenv()

                # Try Vertex AI first (GCP ADC)
                if vertexai:
                    try:
                        project_id = os.getenv('GCP_PROJECT_ID', 'gen-lang-client-0324154376')
                        location = os.getenv('GCP_LOCATION', 'us-central1')
                        vertexai.init(project=project_id, location=location)
                        self._vertex_model = GenerativeModel("gemini-2.5-flash")
                        print(f"Vertex AI configured (project={project_id}, location={location})")
                    except Exception as e:
                        print(f"Vertex AI init failed: {e}")
                        skip_style = True
                # Fallback to google.generativeai with API key
                elif genai:
                    api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
                    if api_key:
                        genai.configure(api_key=api_key)
                        print("Gemini API configured for style normalization")
                    else:
                        print("Warning: No API key found. Skipping style normalization.")
                        skip_style = True
                else:
                    skip_style = True

        # Process each record
        normalized_data = self.data.copy()
        normalized_data['normalized_at'] = datetime.now().isoformat()
        normalized_data['normalization_version'] = '1.0'

        for i, (record_id, record) in enumerate(self.data['summaries'].items()):
            normalized_data['summaries'][record_id] = self.normalize_record(
                record_id, record, skip_style
            )

            # Progress indicator
            if (i + 1) % 500 == 0:
                print(f"  Processed {i + 1}/{self.stats['total']} records...")

        print(f"  Processed {self.stats['total']}/{self.stats['total']} records.")

        # Save results
        if not dry_run:
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(normalized_data, f, ensure_ascii=False, indent=2)
            print(f"\nNormalized data saved to: {self.output_path}")

        # Generate diff report
        self._generate_diff_report(normalized_data, dry_run)

        # Print summary
        self._print_summary()

        return normalized_data

    def _generate_diff_report(self, normalized_data: dict, dry_run: bool):
        """Generate diff report showing changes."""
        report_dir = self.schema_dir.parent / 'reports'
        report_dir.mkdir(parents=True, exist_ok=True)

        changes = {
            'timestamp': datetime.now().isoformat(),
            'dry_run': dry_run,
            'stats': self.stats,
            'tradition_changes': [],
            'period_changes': [],
            'style_pending': []
        }

        for record_id, record in normalized_data['summaries'].items():
            # Tradition changes
            orig_t = record.get('_original_tradition', '')
            new_t = record.get('tradition', '')
            if orig_t != new_t:
                changes['tradition_changes'].append({
                    'id': record_id,
                    'from': orig_t,
                    'to': new_t
                })

            # Period changes
            orig_p = record.get('_original_period', '')
            new_p = record.get('period', '')
            if orig_p != new_p:
                changes['period_changes'].append({
                    'id': record_id,
                    'from': orig_p,
                    'to': new_p
                })

            # Style pending
            if record.get('style_normalization_status') == 'pending':
                changes['style_pending'].append({
                    'id': record_id,
                    'text': record.get('brief_summary', '')[:200]
                })

        # Save JSON report
        prefix = 'dry_run_' if dry_run else ''
        json_path = report_dir / f'{prefix}normalization_changes.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(changes, f, ensure_ascii=False, indent=2)
        print(f"Diff report saved to: {json_path}")

        # Save TSV for failed/pending items
        if self.stats['errors']:
            tsv_path = report_dir / f'{prefix}normalization_errors.tsv'
            with open(tsv_path, 'w', encoding='utf-8') as f:
                f.write("record_id\terror_type\tdetails\n")
                for err in self.stats['errors']:
                    f.write(f"{err['id']}\t{err['type']}\t{err.get('error', '')}\n")
            print(f"Error log saved to: {tsv_path}")

    def _print_summary(self):
        """Print normalization summary."""
        print("\n" + "=" * 60)
        print("NORMALIZATION SUMMARY")
        print("=" * 60)
        print(f"Total Records: {self.stats['total']:,}")
        print(f"\nTradition Changes: {self.stats['tradition_changed']:,}")
        print(f"Period Changes: {self.stats['period_changed']:,}")
        print(f"\nBrief Summary Style Changes: {self.stats['style_changed']:,}")
        print(f"Brief Summary Style Pending: {self.stats['style_pending']:,}")
        print(f"\nDetailed Summary Style Changes: {self.stats['detailed_style_changed']:,}")
        print(f"Detailed Summary Style Pending: {self.stats['detailed_style_pending']:,}")
        print(f"\nErrors: {len(self.stats['errors'])}")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Normalize Tripitaka data')
    parser.add_argument('--data', default='source_explorer/source_data/source_summaries_ko.json',
                        help='Path to source data JSON')
    parser.add_argument('--schema-dir', default='schema',
                        help='Path to schema directory')
    parser.add_argument('--output', default='source_explorer/source_data/source_summaries_ko_normalized.json',
                        help='Output file path')
    parser.add_argument('--dry-run', action='store_true',
                        help='Generate diff report without modifying files')
    parser.add_argument('--skip-style', action='store_true',
                        help='Skip API-based style normalization')
    args = parser.parse_args()

    # Resolve paths relative to script location
    script_dir = Path(__file__).parent
    data_path = script_dir / args.data
    schema_dir = script_dir / args.schema_dir
    output_path = script_dir / args.output

    # Run normalization
    normalizer = TripitakaNormalizer(data_path, schema_dir, output_path)
    normalizer.load_data()
    normalizer.run(dry_run=args.dry_run, skip_style=args.skip_style)


if __name__ == '__main__':
    main()
