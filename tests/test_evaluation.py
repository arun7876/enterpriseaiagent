from pathlib import Path

import pytest

from backend.app.document_processor import process_document
from evaluation.benchmark import run_retrieval_comparison
from evaluation.dataset import (
    EvalCase,
    generate_synthetic_corpus,
    load_eval_dataset,
)
from evaluation.metrics import (
    citation_coverage,
    citation_precision,
    fact_presence_score,
    hit_rate,
    is_refusal_answer,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    refusal_accuracy,
    security_isolation_passed,
)
from evaluation.reporter import generate_reports
from evaluation.runner import EvaluationRunner


def test_metric_hit_rate_hand_calculated() -> None:
    relevant = ["docA.pdf", "docB.docx"]

    assert hit_rate(["docA.pdf", "other.csv"], relevant, k=1) == 1.0
    assert hit_rate(["other.csv", "docB.docx"], relevant, k=1) == 0.0
    assert hit_rate(["other.csv", "docB.docx"], relevant, k=2) == 1.0
    assert hit_rate(["unrelated.pdf"], relevant, k=5) == 0.0
    assert hit_rate([], relevant, k=5) == 0.0


def test_metric_recall_at_k_hand_calculated() -> None:
    relevant = ["docA.pdf", "docB.docx"]

    # Retrieved docA only out of 2 relevant -> recall = 1/2 = 0.5
    assert recall_at_k(["docA.pdf", "other1.pdf"], relevant, k=2) == 0.5
    # Retrieved both -> recall = 2/2 = 1.0
    assert recall_at_k(["docA.pdf", "docB.docx"], relevant, k=2) == 1.0
    # Retrieved docB at rank 3, but k=2 -> recall = 0.0
    assert recall_at_k(["other1.pdf", "other2.pdf", "docB.docx"], relevant, k=2) == 0.0
    # k=3 -> recall = 1/2 = 0.5
    assert recall_at_k(["other1.pdf", "other2.pdf", "docB.docx"], relevant, k=3) == 0.5


def test_metric_precision_at_k_hand_calculated() -> None:
    relevant = ["docA.pdf"]

    # 1 hit in 2 results -> precision = 1/2 = 0.5
    assert precision_at_k(["docA.pdf", "other.pdf"], relevant, k=2) == 0.5
    # 1 hit in 1 result -> precision = 1/1 = 1.0
    assert precision_at_k(["docA.pdf", "other.pdf"], relevant, k=1) == 1.0
    # 0 hit in 2 results -> precision = 0.0
    assert precision_at_k(["other1.pdf", "other2.pdf"], relevant, k=2) == 0.0


def test_metric_reciprocal_rank_hand_calculated() -> None:
    relevant = ["target.pdf"]

    # Target at rank 1 -> MRR = 1/1 = 1.0
    assert reciprocal_rank(["target.pdf", "other.pdf"], relevant) == 1.0
    # Target at rank 2 -> MRR = 1/2 = 0.5
    assert reciprocal_rank(["other1.pdf", "target.pdf"], relevant) == 0.5
    # Target at rank 4 -> MRR = 1/4 = 0.25
    assert reciprocal_rank(["a.pdf", "b.pdf", "c.pdf", "target.pdf"], relevant) == 0.25
    # Not found -> MRR = 0.0
    assert reciprocal_rank(["a.pdf", "b.pdf"], relevant) == 0.0


def test_metric_fact_presence_score() -> None:
    essential = ["$250", "hotel", "economy class"]
    answer = "The domestic hotel allowance is capped at $250. Flights must be economy class."

    # All 3 found -> 1.0
    assert fact_presence_score(answer, essential) == 1.0

    partial_answer = "Hotel allowance is $250."
    # 2 out of 3 found -> 2/3 ≈ 0.667
    assert round(fact_presence_score(partial_answer, essential), 2) == 0.67

    missing_answer = "No details available."
    assert fact_presence_score(missing_answer, essential) == 0.0


def test_metric_refusal_accuracy() -> None:
    refusal_text = "The indexed documents do not provide enough evidence to answer this question."
    hallucinated_text = "The pet insurance reimbursement is $500 per month."

    # When expected_behavior == "refuse"
    assert refusal_accuracy(refusal_text, expected_behavior="refuse", citation_count=0) is True
    assert refusal_accuracy(refusal_text, expected_behavior="refuse", citation_count=1) is False  # Cannot have citations on refusal
    assert refusal_accuracy(hallucinated_text, expected_behavior="refuse", citation_count=0) is False

    # When expected_behavior == "answer"
    assert refusal_accuracy(hallucinated_text, expected_behavior="answer", citation_count=1) is True
    assert refusal_accuracy(refusal_text, expected_behavior="answer", citation_count=0) is False


def test_metric_citation_precision_and_coverage() -> None:
    relevant = ["policy.pdf"]

    # 1 valid citation out of 1 -> 1.0
    assert citation_precision(["policy.pdf"], relevant, "answer") == 1.0
    # 1 valid and 1 hallucinated citation -> 0.5
    assert citation_precision(["policy.pdf", "fake.docx"], relevant, "answer") == 0.5
    # 0 valid citations -> 0.0
    assert citation_precision(["fake.docx"], relevant, "answer") == 0.0

    # Coverage
    assert citation_coverage(["policy.pdf"], "answer") is True
    assert citation_coverage([], "answer") is False
    assert citation_coverage([], "refuse") is True
    assert citation_coverage(["policy.pdf"], "refuse") is False


def test_metric_security_isolation_passed() -> None:
    unauthorized = ["private_payroll.csv"]
    forbidden = ["450000", "Victoria Sterling"]

    # Clean query
    assert security_isolation_passed(
        retrieved_sources=["policy.pdf"],
        cited_sources=["policy.pdf"],
        forbidden_facts=forbidden,
        answer="The hotel rate is $250.",
        unauthorized_sources=unauthorized,
    ) is True

    # Leaked private source in retrieval
    assert security_isolation_passed(
        retrieved_sources=["private_payroll.csv"],
        cited_sources=[],
        forbidden_facts=forbidden,
        answer="I found the payroll file.",
        unauthorized_sources=unauthorized,
    ) is False

    # Leaked forbidden text in answer
    assert security_isolation_passed(
        retrieved_sources=["policy.pdf"],
        cited_sources=["policy.pdf"],
        forbidden_facts=forbidden,
        answer="The salary of Victoria Sterling was found.",
        unauthorized_sources=unauthorized,
    ) is False


def test_eval_dataset_schema_and_case_coverage() -> None:
    dataset = load_eval_dataset()

    assert dataset.version == "1.0.0"
    assert len(dataset.cases) >= 30

    case_ids = [c.case_id for c in dataset.cases]
    assert len(case_ids) == len(set(case_ids)), "Case IDs must be unique"

    categories = {c.category for c in dataset.cases}
    assert "direct_fact" in categories
    assert "multi_section" in categories
    assert "comparison_calculation" in categories
    assert "unsupported_refusal" in categories
    assert "ambiguous" in categories
    assert "cross_document" in categories
    assert "citation_validation" in categories
    assert "security_isolation" in categories

    for case in dataset.cases:
        assert case.question.strip()
        assert case.expected_behavior in {"answer", "refuse", "deny_access"}
        if case.expected_behavior == "answer":
            assert len(case.essential_facts) > 0
            assert len(case.relevant_sources) > 0


def test_corpus_generation_and_document_extraction(tmp_path: Path) -> None:
    corpus = generate_synthetic_corpus(tmp_path)

    assert "acme_corp_travel_policy.pdf" in corpus
    assert "techflow_q3_financial_report.pdf" in corpus
    assert "cloudscale_security_handbook.docx" in corpus
    assert "engineering_onboarding_guide.docx" in corpus
    assert "sales_q3_performance.csv" in corpus
    assert "private_payroll_executive.csv" in corpus

    # Validate that document processor extracts content from all 6 files
    for filename, filepath in corpus.items():
        processed = process_document(filepath, filename)
        assert processed.extraction_status == "success"
        assert len(processed.extracted_text) > 50


def test_deterministic_evaluation_runner_and_reports(tmp_path: Path) -> None:
    index_path = tmp_path / "test_eval_index.sqlite3"
    corpus_dir = tmp_path / "corpus"
    report_dir = tmp_path / "reports"

    runner = EvaluationRunner(
        index_path=index_path,
        corpus_dir=corpus_dir,
        mode="deterministic",
        top_k=5,
    )

    dataset = load_eval_dataset()
    summary = runner.run_suite(dataset)

    assert summary.dataset_size == len(dataset.cases)
    assert summary.mode == "deterministic"
    assert summary.hit_rate >= 0.90
    assert summary.mean_mrr >= 0.80
    assert summary.security_pass_rate == 1.0
    assert summary.latency_mean_ms > 0
    assert summary.latency_p50_ms > 0
    assert summary.latency_p95_ms > 0

    # Test report generation
    json_path, md_path = generate_reports(summary, output_dir=report_dir)
    assert json_path.is_file()
    assert md_path.is_file()
    assert '"dataset_size":' in json_path.read_text(encoding="utf-8")
    assert "# RAG Evaluation" in md_path.read_text(encoding="utf-8")


def test_retrieval_comparison_benchmark(tmp_path: Path) -> None:
    index_path = tmp_path / "comparison_index.sqlite3"
    corpus_dir = tmp_path / "corpus"

    # Run comparison with small k list
    comparison = run_retrieval_comparison(
        index_path=index_path,
        corpus_dir=corpus_dir,
        k_values=(3, 5),
    )

    assert len(comparison.entries) == 2
    assert comparison.entries[0].top_k == 3
    assert comparison.entries[1].top_k == 5
    assert comparison.entries[1].hit_rate >= comparison.entries[0].hit_rate
