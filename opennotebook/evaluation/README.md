# Buddhist RAG Evaluation Framework

Phase 1.1 평가 프레임워크: Golden Set 기반 RAGAS + TruLens 평가

## Quick Start

### 1. Install Dependencies

```bash
cd evaluation
source ../../../venv/bin/activate
pip install -r requirements.txt
```

### 2. Build Golden Set (100 Q&A pairs)

```bash
python golden_set_builder.py
```

이 스크립트는:
- CBETA 경전 요약을 읽고
- Gemini 2.0 Flash로 고품질 Q&A 생성
- Factual, Interpretive, Practical 질문을 골고루 분포
- `golden_set.json`에 저장 (자동 checkpoint)

예상 시간: ~3-5분 (100개 질문, 1.5초/API 호출)

### 3. Run Baseline Benchmark

서버가 실행 중인지 확인:
```bash
cd ..
python main.py
```

별도 터미널에서 벤치마크 실행:
```bash
cd evaluation
python benchmark_suite.py
```

이 스크립트는:
1. Golden Set의 모든 질문을 RAG에 쿼리
2. RAGAS 4가지 지표로 평가:
   - Context Precision (검색 정확도)
   - Context Recall (검색 완전성)
   - Faithfulness (환각 없음)
   - Answer Relevancy (답변 관련성)
3. 결과를 `evaluation_results/`에 저장

### 4. View Results

```bash
ls evaluation_results/
# benchmark_baseline_v1_TIMESTAMP.json
# ragas_results_TIMESTAMP.json
```

결과 JSON에는:
- 모든 질문/답변/contexts
- RAGAS 점수
- 타임스탬프 및 설정

## Directory Structure

```
evaluation/
├── README.md                  # 이 파일
├── requirements.txt           # 의존성
├── golden_set.json            # 100개 Q&A (생성됨)
├── golden_set_builder.py      # Golden Set 생성기
├── ragas_evaluator.py         # RAGAS 평가 시스템
├── trulens_monitor.py         # TruLens 모니터링
├── benchmark_suite.py         # 전체 벤치마크 러너
└── evaluation_results/        # 평가 결과 (생성됨)
    ├── benchmark_*.json
    └── ragas_results_*.json
```

## Usage Examples

### Golden Set만 생성

```python
from golden_set_builder import GoldenSetBuilder

builder = GoldenSetBuilder(
    source_summaries_path="../source_explorer/source_data/source_summaries_ko.json",
    output_path="golden_set.json"
)

builder.build_golden_set(
    target_count=100,
    questions_per_sutra=5
)
```

### RAGAS만 실행

```python
import asyncio
from ragas_evaluator import RAGASEvaluator

evaluator = RAGASEvaluator(golden_set_path="golden_set.json")

# Your RAG responses in format:
responses = [
    {
        'question': '질문',
        'answer': 'RAG 답변',
        'contexts': ['context1', 'context2'],
        'ground_truth': '정답'
    }
]

scores = await evaluator.evaluate_rag_system(responses)
print(scores)
```

### Benchmark 실행 및 비교

```python
import asyncio
from benchmark_suite import BenchmarkSuite

suite = BenchmarkSuite(golden_set_path="golden_set.json")

# Run baseline
baseline = await suite.run_benchmark(experiment_name="baseline_v1")

# Make improvements to your RAG system...

# Run experiment
experiment = await suite.run_benchmark(experiment_name="with_reranker")

# Compare
suite.compare_experiments(
    "evaluation_results/benchmark_baseline_v1_*.json",
    "evaluation_results/benchmark_with_reranker_*.json"
)
```

### TruLens 모니터링 (선택사항)

```python
from trulens_monitor import TruLensMonitor

monitor = TruLensMonitor()

# Wrap your LangChain chain
from langchain.chains import RetrievalQA
chain = RetrievalQA.from_chain_type(...)
monitored_chain = monitor.wrap_chain(chain, app_id="baseline_v1")

# Use normally - TruLens tracks everything
result = monitored_chain({"query": "사성제란?"})

# View dashboard
monitor.start_dashboard(port=8501)
# Visit http://localhost:8501
```

## Metrics Explained

### RAGAS Metrics

1. **Context Precision** (0-1)
   - 검색된 contexts가 질문과 관련 있는가?
   - 높을수록 좋음 (irrelevant contexts 적음)
   - Target: 0.7+

2. **Context Recall** (0-1)
   - Ground truth 답변에 필요한 정보가 contexts에 있는가?
   - 높을수록 좋음 (필요한 정보 누락 없음)
   - Target: 0.8+

3. **Faithfulness** (0-1)
   - 답변이 contexts에 근거하는가? (환각 없음)
   - 높을수록 좋음 (환각 적음)
   - Target: 0.9+

4. **Answer Relevancy** (0-1)
   - 답변이 질문과 관련 있는가?
   - 높을수록 좋음 (off-topic 답변 없음)
   - Target: 0.8+

### TruLens RAG Triad

1. **Context Relevance**: 검색 품질
2. **Groundedness**: 환각 검출
3. **Answer Relevance**: 답변 품질

## Expected Performance Targets

| Metric | Baseline Target | Phase 1 Goal | Phase 3 Goal |
|--------|----------------|--------------|--------------|
| Context Precision | 0.60 | 0.75 (+25%) | 0.85 |
| Context Recall | 0.65 | 0.80 (+23%) | 0.90 |
| Faithfulness | 0.80 | 0.90 (+12%) | 0.95 |
| Answer Relevancy | 0.70 | 0.85 (+21%) | 0.90 |

## Troubleshooting

### "RAGAS not installed"
```bash
pip install ragas datasets
```

### "TruLens not installed"
```bash
pip install trulens-eval
# Set OPENAI_API_KEY for TruLens evaluations
export OPENAI_API_KEY=your_key
```

### "RAG server not running"
```bash
cd /Users/vairocana/Desktop/buddhakorea/buddha-korea-notebook-exp/opennotebook
source ../../venv/bin/activate
python main.py
```

### Golden Set 생성이 느림
- `RATE_LIMIT_DELAY`를 조정 (golden_set_builder.py:272)
- 현재: 1.5초/요청 = ~3분 for 100 questions
- Gemini 2.0 Flash quota: 300 req/min

## Next Steps

Phase 1.1 완료 후:
1. ✅ Golden Set 100개 구축
2. ✅ Baseline 벤치마크 실행
3. → Phase 1.2: Reranker 통합
4. → Phase 1.3: Anti-hallucination prompt
5. → Phase 2: Redis caching + HyDE
