from pathlib import Path
from typing import Sequence

from pydantic import BaseModel

from evaluation.dataset import EvalDataset, load_eval_dataset
from evaluation.runner import EvaluationRunner, EvaluationSummary


class ConfigComparisonEntry(BaseModel):
    config_name: str
    top_k: int
    hit_rate: float
    mean_recall_at_k: float
    mean_precision_at_k: float
    mean_mrr: float
    overall_pass_rate: float
    retrieval_latency_mean_ms: float
    latency_p95_ms: float


class BenchmarkComparisonReport(BaseModel):
    baseline_top_k: int
    entries: list[ConfigComparisonEntry]
    notes: str


def run_retrieval_comparison(
    index_path: Path,
    corpus_dir: Path | None = None,
    k_values: Sequence[int] = (3, 5, 8),
    dataset: EvalDataset | None = None,
    mode: str = "deterministic",
) -> BenchmarkComparisonReport:
    """Compares retrieval quality and latency across different top_k values."""
    ds = dataset or load_eval_dataset()
    entries: list[ConfigComparisonEntry] = []

    for k in k_values:
        runner = EvaluationRunner(
            index_path=index_path,
            corpus_dir=corpus_dir,
            mode=mode,  # type: ignore
            top_k=k,
        )
        summary: EvaluationSummary = runner.run_suite(ds)
        entries.append(
            ConfigComparisonEntry(
                config_name=f"top_k={k}" + (" (Baseline)" if k == 5 else ""),
                top_k=k,
                hit_rate=summary.hit_rate,
                mean_recall_at_k=summary.mean_recall_at_k,
                mean_precision_at_k=summary.mean_precision_at_k,
                mean_mrr=summary.mean_mrr,
                overall_pass_rate=summary.overall_pass_rate,
                retrieval_latency_mean_ms=summary.retrieval_latency_mean_ms,
                latency_p95_ms=summary.latency_p95_ms,
            )
        )

    return BenchmarkComparisonReport(
        baseline_top_k=5,
        entries=entries,
        notes="Compared top_k values (3, 5, 8) over synthetic enterprise dataset. Higher k increases recall and hit rate on multi-source queries at the expense of retrieval latency.",
    )
