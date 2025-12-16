"""
Benchmark Suite for Buddhist RAG System
Runs golden set through RAG system and evaluates with RAGAS + TruLens
"""

import json
import os
import sys
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
from loguru import logger
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent / '.env')

# Local imports
from ragas_evaluator import RAGASEvaluator, RAGAS_AVAILABLE
from trulens_monitor import TruLensMonitor, TRULENS_AVAILABLE

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO")


class BenchmarkSuite:
    """End-to-end benchmark suite for RAG evaluation"""

    def __init__(
        self,
        golden_set_path: str,
        rag_api_url: str = "http://localhost:8000",
        results_dir: str = "./evaluation_results"
    ):
        self.golden_set_path = golden_set_path
        self.rag_api_url = rag_api_url
        self.results_dir = results_dir
        os.makedirs(results_dir, exist_ok=True)

        # Load golden set
        with open(golden_set_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.questions = data['questions']

        logger.info(f"✓ Loaded {len(self.questions)} questions from golden set")

    def query_rag_system(
        self,
        question: str,
        sutra_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """Query the RAG system via API"""

        payload = {"query": question}
        if sutra_filter:
            payload["sutra_filter"] = sutra_filter

        try:
            response = requests.post(
                f"{self.rag_api_url}/api/chat",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to query RAG: {e}")
            return None

    async def run_benchmark(
        self,
        experiment_name: str = "baseline",
        use_sutra_filter: bool = True,
        sample_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Run full benchmark: query RAG + evaluate with RAGAS

        Args:
            experiment_name: Name for this experiment
            use_sutra_filter: Whether to use sutra_id filtering
            sample_size: If set, only use first N questions

        Returns:
            Benchmark results dict
        """

        logger.info(f"\n{'='*60}")
        logger.info(f"🔬 Running Benchmark: {experiment_name}")
        logger.info(f"{'='*60}\n")

        # Sample questions if requested
        questions_to_test = self.questions[:sample_size] if sample_size else self.questions
        logger.info(f"Testing {len(questions_to_test)} questions")

        # Query RAG for each question
        rag_responses = []
        errors = 0

        for i, qa_pair in enumerate(questions_to_test, 1):
            question = qa_pair['question']
            ground_truth = qa_pair['answer']
            sutra_id = qa_pair.get('sutra_id') if use_sutra_filter else None

            logger.info(f"[{i}/{len(questions_to_test)}] {question[:50]}...")

            # Query RAG
            rag_result = self.query_rag_system(question, sutra_filter=sutra_id)

            if rag_result is None:
                logger.error(f"  ✗ Query failed")
                errors += 1
                continue

            # Extract answer and contexts
            rag_answer = rag_result.get('response', '')
            sources = rag_result.get('sources', [])
            contexts = [src.get('excerpt', '') for src in sources]

            rag_responses.append({
                'question': question,
                'answer': rag_answer,
                'contexts': contexts,
                'ground_truth': ground_truth,
                'sutra_id': sutra_id,
                'category': qa_pair.get('category', 'unknown')
            })

            logger.info(f"  ✓ Got response ({len(contexts)} contexts)")

            # Rate limiting
            await asyncio.sleep(0.5)

        logger.info(f"\n✓ RAG queries complete: {len(rag_responses)} successful, {errors} errors")

        # Evaluate with RAGAS
        ragas_scores = {}
        if RAGAS_AVAILABLE and len(rag_responses) > 0:
            logger.info("\n" + "="*60)
            logger.info("📊 Running RAGAS Evaluation")
            logger.info("="*60 + "\n")

            evaluator = RAGASEvaluator(
                golden_set_path=self.golden_set_path,
                results_dir=self.results_dir
            )

            ragas_scores = await evaluator.evaluate_rag_system(
                rag_responses,
                save_results=True
            )

        # Compile results
        results = {
            'experiment_name': experiment_name,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'config': {
                'use_sutra_filter': use_sutra_filter,
                'total_questions': len(questions_to_test),
                'successful_queries': len(rag_responses),
                'errors': errors
            },
            'ragas_scores': ragas_scores,
            'responses': rag_responses
        }

        # Save results
        output_path = os.path.join(
            self.results_dir,
            f"benchmark_{experiment_name}_{time.strftime('%Y%m%d_%H%M%S')}.json"
        )

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        logger.info(f"\n💾 Benchmark results saved to: {output_path}")

        # Print summary
        self._print_summary(results)

        return results

    def _print_summary(self, results: Dict[str, Any]):
        """Print benchmark summary"""

        logger.info("\n" + "="*60)
        logger.info(f"📈 Benchmark Summary: {results['experiment_name']}")
        logger.info("="*60)

        config = results['config']
        logger.info(f"\n📋 Configuration:")
        logger.info(f"  Sutra Filter: {config['use_sutra_filter']}")
        logger.info(f"  Total Questions: {config['total_questions']}")
        logger.info(f"  Successful: {config['successful_queries']}")
        logger.info(f"  Errors: {config['errors']}")

        if results['ragas_scores']:
            scores = results['ragas_scores']
            logger.info(f"\n📊 RAGAS Scores:")
            logger.info(f"  Context Precision: {scores.get('context_precision', 0):.3f}")
            logger.info(f"  Context Recall: {scores.get('context_recall', 0):.3f}")
            logger.info(f"  Faithfulness: {scores.get('faithfulness', 0):.3f}")
            logger.info(f"  Answer Relevancy: {scores.get('answer_relevancy', 0):.3f}")

        logger.info("\n" + "="*60 + "\n")

    def compare_experiments(
        self,
        baseline_path: str,
        experiment_path: str
    ):
        """Compare two benchmark results"""

        with open(baseline_path, 'r', encoding='utf-8') as f:
            baseline = json.load(f)

        with open(experiment_path, 'r', encoding='utf-8') as f:
            experiment = json.load(f)

        logger.info("\n" + "="*60)
        logger.info(f"📊 Comparing: {baseline['experiment_name']} vs {experiment['experiment_name']}")
        logger.info("="*60)

        # Compare RAGAS scores
        if baseline['ragas_scores'] and experiment['ragas_scores']:
            logger.info("\n📈 RAGAS Score Changes:\n")

            for metric in baseline['ragas_scores'].keys():
                base_score = baseline['ragas_scores'][metric]
                exp_score = experiment['ragas_scores'][metric]
                delta = exp_score - base_score
                delta_pct = (delta / base_score * 100) if base_score > 0 else 0

                direction = "📈" if delta > 0 else "📉" if delta < 0 else "➡️"
                logger.info(
                    f"  {metric:20s}: {base_score:.3f} → {exp_score:.3f} "
                    f"{direction} {delta:+.3f} ({delta_pct:+.1f}%)"
                )

        logger.info("\n" + "="*60 + "\n")


async def main():
    """Run baseline benchmark"""

    # Check if RAG server is running
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        logger.info("✓ RAG server is running")
    except:
        logger.error("✗ RAG server not running on localhost:8000")
        logger.error("  Start server with: cd ../opennotebook && python main.py")
        sys.exit(1)

    # Initialize benchmark suite
    suite = BenchmarkSuite(
        golden_set_path="golden_set.json",
        rag_api_url="http://localhost:8000"
    )

    # Run baseline benchmark
    results = await suite.run_benchmark(
        experiment_name="baseline_v1",
        use_sutra_filter=True,
        sample_size=20  # Start with 20 questions for quick test
    )

    logger.info("\n✅ Baseline benchmark complete!")
    logger.info("Next steps:")
    logger.info("  1. Review results in ./evaluation_results/")
    logger.info("  2. Make improvements to RAG system")
    logger.info("  3. Run new benchmark with different experiment_name")
    logger.info("  4. Compare results with suite.compare_experiments()")


if __name__ == "__main__":
    if not RAGAS_AVAILABLE:
        logger.error("Please install RAGAS: pip install ragas")
        sys.exit(1)

    asyncio.run(main())
