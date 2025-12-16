"""
Re-calculate RAGAS scores from already-collected RAG responses
This is faster than re-querying the entire RAG system
"""
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / '.env')

from ragas_evaluator import RAGASEvaluator

# Load the most recent benchmark results
result_files = list(Path("evaluation_results").glob("benchmark_*.json"))
if not result_files:
    print("No benchmark files found")
    exit(1)

latest_file = max(result_files, key=lambda p: p.stat().st_mtime)
print(f"Loading: {latest_file}")

with open(latest_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

responses = data['responses']
print(f"Found {len(responses)} RAG responses")

# Create evaluator
evaluator = RAGASEvaluator(
    golden_set_path="golden_set.json",
    results_dir="./evaluation_results"
)

# Re-run RAGAS evaluation with fixed score extraction
async def main():
    scores = await evaluator.evaluate_rag_system(
        responses,
        save_results=True
    )

    print("\n" + "="*60)
    print("✅ RECALCULATED SCORES (Fixed Extraction)")
    print("="*60)
    print(f"  Context Precision: {scores['context_precision']:.3f}")
    print(f"  Context Recall: {scores['context_recall']:.3f}")
    print(f"  Faithfulness: {scores['faithfulness']:.3f}")
    print(f"  Answer Relevancy: {scores['answer_relevancy']:.3f}")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
