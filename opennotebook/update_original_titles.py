#!/usr/bin/env python3
"""
Update original_title field in source_summaries_ko.json with correct Chinese titles from cbeta_titles_complete.json
"""
import json
from pathlib import Path

def main():
    # File paths
    base_dir = Path(__file__).parent
    cbeta_file = base_dir / "data" / "raw" / "cbeta" / "cbeta_titles_complete.json"
    summaries_file = base_dir / "source_explorer" / "source_data" / "source_summaries_ko.json"

    # Load both JSON files
    print(f"Loading {cbeta_file}...")
    with open(cbeta_file, 'r', encoding='utf-8') as f:
        cbeta_data = json.load(f)

    print(f"Loading {summaries_file}...")
    with open(summaries_file, 'r', encoding='utf-8') as f:
        summaries_data = json.load(f)

    # Statistics
    total_sutras = len(summaries_data['summaries'])
    updated_count = 0
    not_found_count = 0
    unchanged_count = 0

    print(f"\nProcessing {total_sutras} sutras...")

    # Update original_title field
    for sutra_id, summary in summaries_data['summaries'].items():
        if sutra_id in cbeta_data['sutras']:
            old_title = summary.get('original_title', '')
            new_title = cbeta_data['sutras'][sutra_id]['title_zh']

            if old_title != new_title:
                summary['original_title'] = new_title
                updated_count += 1

                # Show first 5 updates as examples
                if updated_count <= 5:
                    print(f"  {sutra_id}: '{old_title}' → '{new_title}'")
            else:
                unchanged_count += 1
        else:
            not_found_count += 1
            if not_found_count <= 5:
                print(f"  Warning: {sutra_id} not found in cbeta_titles_complete.json")

    # Save updated file
    print(f"\nSaving updated file to {summaries_file}...")
    with open(summaries_file, 'w', encoding='utf-8') as f:
        json.dump(summaries_data, f, ensure_ascii=False, indent=2)

    # Print summary
    print("\n" + "="*60)
    print("UPDATE SUMMARY")
    print("="*60)
    print(f"Total sutras in summaries:        {total_sutras}")
    print(f"Updated (title changed):          {updated_count}")
    print(f"Unchanged (already correct):      {unchanged_count}")
    print(f"Not found in CBETA titles:        {not_found_count}")
    print("="*60)
    print("\n✅ Update completed successfully!")

    # Show some examples of updated entries
    print("\nSample updated entries:")
    sample_ids = ['T01n0001', 'T01n0004', 'T01n0005']
    for sutra_id in sample_ids:
        if sutra_id in summaries_data['summaries']:
            entry = summaries_data['summaries'][sutra_id]
            print(f"\n{sutra_id}:")
            print(f"  한글: {entry.get('title_ko', 'N/A')}")
            print(f"  중문: {entry.get('original_title', 'N/A')}")

if __name__ == '__main__':
    main()
