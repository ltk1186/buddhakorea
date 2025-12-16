"""
TruLens RAG Triad Monitor for Buddhist RAG System
Tracks: Context Relevance, Groundedness, Answer Relevance
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from loguru import logger

# TruLens imports
try:
    from trulens_eval import Tru, Feedback, TruChain
    from trulens_eval.feedback import Groundedness
    from trulens_eval.feedback.provider.openai import OpenAI as TruOpenAI
    TRULENS_AVAILABLE = True
except ImportError:
    logger.warning("TruLens not installed. Install with: pip install trulens-eval")
    TRULENS_AVAILABLE = False

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO")


class TruLensMonitor:
    """Monitor RAG system with TruLens RAG Triad"""

    def __init__(
        self,
        db_path: str = "./trulens_db",
        app_name: str = "BuddhistRAG"
    ):
        if not TRULENS_AVAILABLE:
            raise ImportError("TruLens is required. Install with: pip install trulens-eval")

        self.db_path = db_path
        self.app_name = app_name

        # Initialize TruLens
        self.tru = Tru(database_url=f"sqlite:///{db_path}/trulens.db")
        self.tru.reset_database()  # Start fresh

        # Initialize feedback provider (using OpenAI for evaluation)
        # Note: You'll need OPENAI_API_KEY in environment
        try:
            self.provider = TruOpenAI()
            logger.info("✓ TruLens initialized with OpenAI provider")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI provider: {e}")
            logger.error("Set OPENAI_API_KEY environment variable")
            raise

        # Setup RAG Triad feedbacks
        self._setup_feedbacks()

    def _setup_feedbacks(self):
        """Setup RAG Triad feedback functions"""

        # 1. Context Relevance: Are retrieved contexts relevant to the question?
        self.f_context_relevance = (
            Feedback(self.provider.context_relevance)
            .on_input()
            .on(TruChain.select_context())
            .aggregate(lambda x: sum(x) / len(x) if x else 0)
        )

        # 2. Groundedness: Is the answer grounded in the retrieved contexts?
        groundedness = Groundedness(groundedness_provider=self.provider)
        self.f_groundedness = (
            Feedback(groundedness.groundedness_measure_with_cot_reasons)
            .on(TruChain.select_context())
            .on_output()
            .aggregate(lambda x: sum(x) / len(x) if x else 0)
        )

        # 3. Answer Relevance: Is the answer relevant to the question?
        self.f_answer_relevance = (
            Feedback(self.provider.relevance)
            .on_input()
            .on_output()
        )

        logger.info("✓ RAG Triad feedbacks configured:")
        logger.info("  1. Context Relevance (retrieval quality)")
        logger.info("  2. Groundedness (hallucination detection)")
        logger.info("  3. Answer Relevance (answer quality)")

    def wrap_chain(self, chain: Any, app_id: str = None) -> Any:
        """Wrap LangChain chain with TruLens monitoring"""

        if app_id is None:
            import time
            app_id = f"{self.app_name}_{int(time.time())}"

        tru_chain = TruChain(
            chain,
            app_id=app_id,
            feedbacks=[
                self.f_context_relevance,
                self.f_groundedness,
                self.f_answer_relevance
            ]
        )

        logger.info(f"✓ Chain wrapped with TruLens monitoring (app_id: {app_id})")
        return tru_chain

    def get_leaderboard(self) -> Any:
        """Get TruLens leaderboard with all tracked apps"""
        return self.tru.get_leaderboard()

    def get_records(self, app_id: str = None) -> List[Dict]:
        """Get evaluation records for an app"""
        if app_id:
            records = self.tru.get_records_and_feedback(app_ids=[app_id])
        else:
            records = self.tru.get_records_and_feedback()

        return records

    def print_summary(self, app_id: str = None):
        """Print summary statistics"""

        leaderboard = self.get_leaderboard()

        if app_id:
            leaderboard = leaderboard[leaderboard['app_id'] == app_id]

        if len(leaderboard) == 0:
            logger.warning("No evaluation data found")
            return

        logger.info("\n📊 TruLens RAG Triad Summary:")
        for _, row in leaderboard.iterrows():
            logger.info(f"\nApp: {row['app_id']}")
            logger.info(f"  Context Relevance: {row.get('Context Relevance', 'N/A'):.3f}")
            logger.info(f"  Groundedness: {row.get('Groundedness', 'N/A'):.3f}")
            logger.info(f"  Answer Relevance: {row.get('Answer Relevance', 'N/A'):.3f}")
            logger.info(f"  Total Records: {row.get('Records', 0)}")

    def export_results(self, output_path: str, app_id: str = None):
        """Export results to JSON"""

        records = self.get_records(app_id)
        leaderboard = self.get_leaderboard()

        if app_id:
            leaderboard = leaderboard[leaderboard['app_id'] == app_id]

        output = {
            'leaderboard': leaderboard.to_dict(orient='records'),
            'records': records.to_dict(orient='records') if hasattr(records, 'to_dict') else []
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        logger.info(f"💾 Results exported to: {output_path}")

    def start_dashboard(self, port: int = 8501):
        """Start TruLens dashboard"""
        logger.info(f"🚀 Starting TruLens dashboard on port {port}...")
        logger.info(f"   Visit: http://localhost:{port}")
        self.tru.run_dashboard(port=port)


def example_usage():
    """Example of how to use TruLensMonitor"""

    if not TRULENS_AVAILABLE:
        logger.error("Please install TruLens: pip install trulens-eval")
        sys.exit(1)

    # Initialize monitor
    monitor = TruLensMonitor()

    # In your RAG pipeline, wrap your chain:
    # from langchain.chains import RetrievalQA
    # chain = RetrievalQA.from_chain_type(...)
    # monitored_chain = monitor.wrap_chain(chain, app_id="baseline_v1")

    # Then use the monitored chain normally:
    # result = monitored_chain({"query": "사성제란 무엇인가요?"})

    # View results
    # monitor.print_summary()
    # monitor.start_dashboard()

    logger.info("TruLens Monitor ready. Use wrap_chain() in your RAG pipeline.")


if __name__ == "__main__":
    example_usage()
