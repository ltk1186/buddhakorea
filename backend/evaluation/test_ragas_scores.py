"""
Test script to inspect RAGAS result object structure
"""
import os
import sys
from pathlib import Path
from datasets import Dataset
from dotenv import load_dotenv

# Load environment
load_dotenv(Path(__file__).parent.parent / '.env')

from ragas import evaluate
from ragas.metrics import (
    context_precision,
    context_recall,
    faithfulness,
    answer_relevancy
)
from langchain_openai import ChatOpenAI

# Create minimal test dataset
test_data = {
    'question': ['사성제란 무엇인가요?'],
    'answer': ['사성제는 불교의 핵심 가르침으로, 고(苦), 집(集), 멸(滅), 도(道)의 네 가지 성스러운 진리를 말합니다.'],
    'contexts': [['사성제는 부처님께서 깨달으신 네 가지 진리입니다.', '고제는 삶의 고통을 말하며, 집제는 고통의 원인을 말합니다.']],
    'ground_truth': ['사성제는 불교의 기본 교리로 고(苦), 집(集), 멸(滅), 도(道)를 의미합니다.']
}

dataset = Dataset.from_dict(test_data)

print("Running RAGAS evaluation on test dataset...")
evaluator_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

result = evaluate(
    dataset,
    metrics=[
        context_precision,
        context_recall,
        faithfulness,
        answer_relevancy
    ],
    llm=evaluator_llm
)

print("\n" + "="*60)
print("RESULT OBJECT INSPECTION")
print("="*60)

print(f"\nResult type: {type(result)}")
print(f"Result attributes: {dir(result)}")

if hasattr(result, 'scores'):
    print(f"\nresult.scores type: {type(result.scores)}")
    print(f"result.scores:\n{result.scores}")

if hasattr(result, '_scores_dict'):
    print(f"\nresult._scores_dict type: {type(result._scores_dict)}")
    print(f"result._scores_dict: {result._scores_dict}")

if hasattr(result, 'dataset'):
    print(f"\nresult.dataset columns: {result.dataset.column_names}")
    print(f"result.dataset first row: {result.dataset[0]}")

print("\n" + "="*60)
print("EXTRACTION TEST")
print("="*60)

# Test different extraction methods
try:
    print("\nMethod 1: result.scores.to_dict()")
    scores_dict = result.scores.to_dict()
    print(f"  context_precision: {scores_dict.get('context_precision', 'NOT FOUND')}")
    print(f"  context_recall: {scores_dict.get('context_recall', 'NOT FOUND')}")
    print(f"  faithfulness: {scores_dict.get('faithfulness', 'NOT FOUND')}")
    print(f"  answer_relevancy: {scores_dict.get('answer_relevancy', 'NOT FOUND')}")
except Exception as e:
    print(f"  ERROR: {e}")

try:
    print("\nMethod 2: result.scores bracket notation")
    print(f"  context_precision: {result.scores['context_precision']}")
    print(f"  context_recall: {result.scores['context_recall']}")
    print(f"  faithfulness: {result.scores['faithfulness']}")
    print(f"  answer_relevancy: {result.scores['answer_relevancy']}")
except Exception as e:
    print(f"  ERROR: {e}")

try:
    print("\nMethod 3: Check dataset columns for scores")
    if hasattr(result, 'dataset'):
        for col in result.dataset.column_names:
            if col in ['context_precision', 'context_recall', 'faithfulness', 'answer_relevancy']:
                print(f"  {col}: {result.dataset[col][0]}")
except Exception as e:
    print(f"  ERROR: {e}")

print("\nDone!")
