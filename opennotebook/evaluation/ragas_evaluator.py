"""
RAGAS Evaluation System for Buddhist RAG
Measures: Context Precision, Context Recall, Faithfulness, Answer Relevance
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from loguru import logger
import asyncio
from datasets import Dataset

# RAGAS imports
try:
    from ragas import evaluate
    from ragas.metrics import (
        context_precision,
        context_recall,
        faithfulness,
        answer_relevancy
    )
    from ragas.llms import LangchainLLMWrapper
    from langchain_openai import ChatOpenAI
    RAGAS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"RAGAS not installed: {e}. Install with: pip install ragas langchain-openai")
    RAGAS_AVAILABLE = False

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO")


class RAGASEvaluator:
    """Evaluates RAG system using RAGAS metrics"""

    def __init__(
        self,
        golden_set_path: str,
        results_dir: str = "./evaluation_results"
    ):
        self.golden_set_path = golden_set_path
        self.results_dir = results_dir
        os.makedirs(results_dir, exist_ok=True)

        if not RAGAS_AVAILABLE:
            raise ImportError("RAGAS is required. Install with: pip install ragas")

    def load_golden_set(self) -> List[Dict[str, Any]]:
        """Load golden evaluation set"""
        with open(self.golden_set_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['questions']

    async def evaluate_rag_system(
        self,
        rag_responses: List[Dict[str, Any]],
        save_results: bool = True
    ) -> Dict[str, float]:
        """
        Evaluate RAG system using RAGAS metrics

        Args:
            rag_responses: List of dicts with:
                - question: str
                - answer: str (RAG generated)
                - contexts: List[str] (retrieved contexts)
                - ground_truth: str (golden answer)

        Returns:
            Dict with metric scores
        """

        logger.info(f"Evaluating {len(rag_responses)} responses with RAGAS...")

        # Convert to RAGAS dataset format
        dataset_dict = {
            'question': [],
            'answer': [],
            'contexts': [],
            'ground_truth': []
        }

        for resp in rag_responses:
            dataset_dict['question'].append(resp['question'])
            dataset_dict['answer'].append(resp['answer'])
            dataset_dict['contexts'].append(resp['contexts'])
            dataset_dict['ground_truth'].append(resp['ground_truth'])

        dataset = Dataset.from_dict(dataset_dict)

        # Run RAGAS evaluation
        logger.info("Running RAGAS evaluation (this may take a few minutes)...")

        # Configure OpenAI LLM for evaluation
        evaluator_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

        # RAGAS 0.3+ evaluate() is not async
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

        # Extract scores - handle different result formats
        try:
            # RAGAS 0.3+ returns an EvaluationResult object
            # result._scores_dict contains per-sample scores as lists
            # We need to calculate the mean across all samples

            if hasattr(result, '_scores_dict'):
                import numpy as np
                scores_dict = result._scores_dict

                # Calculate mean for each metric
                scores = {
                    'context_precision': float(np.mean(scores_dict.get('context_precision', [0.0]))),
                    'context_recall': float(np.mean(scores_dict.get('context_recall', [0.0]))),
                    'faithfulness': float(np.mean(scores_dict.get('faithfulness', [0.0]))),
                    'answer_relevancy': float(np.mean(scores_dict.get('answer_relevancy', [0.0])))
                }

                logger.info(f"Extracted scores from {len(scores_dict.get('context_precision', []))} samples")

            elif hasattr(result, 'scores') and isinstance(result.scores, list):
                # Alternative: scores is a list of dicts
                import numpy as np
                scores_list = result.scores

                # Calculate mean across all samples
                scores = {
                    'context_precision': float(np.mean([s.get('context_precision', 0.0) for s in scores_list])),
                    'context_recall': float(np.mean([s.get('context_recall', 0.0) for s in scores_list])),
                    'faithfulness': float(np.mean([s.get('faithfulness', 0.0) for s in scores_list])),
                    'answer_relevancy': float(np.mean([s.get('answer_relevancy', 0.0) for s in scores_list]))
                }

                logger.info(f"Extracted scores from {len(scores_list)} samples")

            else:
                logger.error("Could not find scores in result object")
                logger.info(f"Result type: {type(result)}")
                logger.info(f"Result attributes: {dir(result)}")
                scores = {
                    'context_precision': 0.0,
                    'context_recall': 0.0,
                    'faithfulness': 0.0,
                    'answer_relevancy': 0.0
                }

        except Exception as e:
            logger.error(f"Error extracting scores: {e}")
            logger.info(f"Result type: {type(result)}")
            if hasattr(result, '__dict__'):
                logger.info(f"Result dict: {result.__dict__}")
            raise

        logger.success("✓ RAGAS evaluation complete!")
        logger.info(f"\n📊 Results:")
        logger.info(f"  Context Precision: {scores['context_precision']:.3f}")
        logger.info(f"  Context Recall: {scores['context_recall']:.3f}")
        logger.info(f"  Faithfulness: {scores['faithfulness']:.3f}")
        logger.info(f"  Answer Relevancy: {scores['answer_relevancy']:.3f}")

        if save_results:
            self._save_results(scores, rag_responses)

        return scores

    def _save_results(
        self,
        scores: Dict[str, float],
        responses: List[Dict[str, Any]]
    ):
        """Save evaluation results to JSON"""
        import time

        output = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_questions': len(responses),
            'metrics': scores,
            'responses': responses
        }

        output_path = os.path.join(
            self.results_dir,
            f"ragas_results_{time.strftime('%Y%m%d_%H%M%S')}.json"
        )

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        logger.info(f"\n💾 Results saved to: {output_path}")

    def compare_results(
        self,
        baseline_path: str,
        experiment_path: str
    ) -> Dict[str, Dict[str, float]]:
        """Compare two evaluation results"""

        with open(baseline_path, 'r', encoding='utf-8') as f:
            baseline = json.load(f)

        with open(experiment_path, 'r', encoding='utf-8') as f:
            experiment = json.load(f)

        comparison = {}
        for metric in baseline['metrics'].keys():
            baseline_score = baseline['metrics'][metric]
            experiment_score = experiment['metrics'][metric]
            delta = experiment_score - baseline_score
            delta_pct = (delta / baseline_score) * 100 if baseline_score > 0 else 0

            comparison[metric] = {
                'baseline': baseline_score,
                'experiment': experiment_score,
                'delta': delta,
                'delta_pct': delta_pct
            }

        logger.info("\n📈 Comparison Results:")
        for metric, data in comparison.items():
            direction = "📈" if data['delta'] > 0 else "📉" if data['delta'] < 0 else "➡️"
            logger.info(
                f"  {metric}: {data['baseline']:.3f} → {data['experiment']:.3f} "
                f"{direction} {data['delta']:+.3f} ({data['delta_pct']:+.1f}%)"
            )

        return comparison


async def main():
    """Example usage"""
    evaluator = RAGASEvaluator(golden_set_path="golden_set.json")

    # Example RAG responses (you would get these from your RAG system)
    example_responses = [
        {
            'question': '사성제란 무엇인가요?',
            'answer': '사성제는 불교의 핵심 가르침으로, 고(苦), 집(集), 멸(滅), 도(道)의 네 가지 성스러운 진리를 말합니다.',
            'contexts': [
                '사성제는 부처님께서 깨달으신 네 가지 진리입니다.',
                '고제는 삶의 고통을 말하며, 집제는 고통의 원인을 말합니다.'
            ],
            'ground_truth': '사성제는 불교의 기본 교리로 고(苦), 집(集), 멸(滅), 도(道)를 의미합니다.'
        }
    ]

    # scores = await evaluator.evaluate_rag_system(example_responses)
    logger.info("RAGAS Evaluator ready. Import and use in your evaluation pipeline.")


if __name__ == "__main__":
    if not RAGAS_AVAILABLE:
        logger.error("Please install RAGAS: pip install ragas")
        sys.exit(1)

    asyncio.run(main())
