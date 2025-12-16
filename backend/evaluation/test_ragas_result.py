"""
Quick test to examine RAGAS result structure
"""
import json

# Load a saved result to inspect structure
with open('evaluation_results/benchmark_baseline_v1_20251108_154714.json', 'r') as f:
    data = json.load(f)

# Check what responses look like
print("Number of responses:", len(data['responses']))
print("\nFirst response structure:")
first_resp = data['responses'][0]
print(f"Question: {first_resp['question'][:50]}...")
print(f"Answer length: {len(first_resp['answer'])}")
print(f"Contexts: {len(first_resp['contexts'])}")
print(f"Ground truth length: {len(first_resp['ground_truth'])}")

# The issue is that RAGAS returned all zeros
# Let's manually check if the data format is correct for RAGAS
print("\n" + "="*60)
print("Dataset format check:")
print(f"  - Has question: {'question' in first_resp}")
print(f"  - Has answer: {'answer' in first_resp}")
print(f"  - Has contexts (list): {isinstance(first_resp['contexts'], list)}")
print(f"  - Has ground_truth: {'ground_truth' in first_resp}")
print(f"  - Contexts non-empty: {len(first_resp['contexts']) > 0}")
print(f"  - First context sample: {first_resp['contexts'][0][:100]}...")
