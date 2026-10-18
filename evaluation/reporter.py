import json
from datetime import datetime, timezone
from pathlib import Path

from evaluation.benchmark import BenchmarkComparisonReport
from evaluation.runner import EvaluationSummary


def generate_markdown_report(
    summary: EvaluationSummary,
    comparison: BenchmarkComparisonReport | None = None,
) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        "# RAG Evaluation and Performance Benchmark Report",
        "",
        f"**Generated:** {timestamp}  ",
        f"**Evaluation Mode:** `{summary.mode}`  ",
        f"**Dataset Size:** {summary.dataset_size} cases  ",
        f"**Top-K Retrieval Parameter:** {summary.top_k}  ",
        "",
        "## 1. Executive Summary",
        "",
        "| Metric | Result | Target | Status |",
        "| :--- | :--- | :--- | :--- |",
        f"| **Overall Pass Rate** | {summary.overall_pass_rate * 100:.1f}% | $\\ge 90.0\\%$ | {'PASS' if summary.overall_pass_rate >= 0.90 else 'WARN'} |",
        f"| **Retrieval Hit Rate** | {summary.hit_rate * 100:.1f}% | $\\ge 95.0\\%$ | {'PASS' if summary.hit_rate >= 0.95 else 'WARN'} |",
        f"| **Mean Recall@{summary.top_k}** | {summary.mean_recall_at_k * 100:.1f}% | $\\ge 90.0\\%$ | {'PASS' if summary.mean_recall_at_k >= 0.90 else 'WARN'} |",
        f"| **Mean Reciprocal Rank (MRR)** | {summary.mean_mrr:.3f} | $\\ge 0.850$ | {'PASS' if summary.mean_mrr >= 0.850 else 'WARN'} |",
        f"| **Factual Coverage** | {summary.mean_fact_score * 100:.1f}% | $\\ge 85.0\\%$ | {'PASS' if summary.mean_fact_score >= 0.85 else 'WARN'} |",
        f"| **Refusal Accuracy (Ungrounded/Unsupported)** | {summary.refusal_accuracy * 100:.1f}% | $100.0\\%$ | {'PASS' if summary.refusal_accuracy == 1.0 else 'WARN'} |",
        f"| **Citation Precision** | {summary.citation_precision * 100:.1f}% | $\\ge 95.0\\%$ | {'PASS' if summary.citation_precision >= 0.95 else 'WARN'} |",
        f"| **Security & Permission Isolation** | {summary.security_pass_rate * 100:.1f}% | $100.0\\%$ | {'PASS' if summary.security_pass_rate == 1.0 else 'FAIL'} |",
        "",
        "## 2. Latency & Resource Benchmarks",
        "",
        "| Latency Metric | Measured Value | Notes |",
        "| :--- | :--- | :--- |",
        f"| **Median Latency (p50)** | {summary.latency_p50_ms} ms | Typical response time |",
        f"| **95th Percentile Latency (p95)** | {summary.latency_p95_ms} ms | Tail latency bound |",
        f"| **Mean Total Latency** | {summary.latency_mean_ms} ms | End-to-end average |",
        f"| **Mean Retrieval Latency** | {summary.retrieval_latency_mean_ms} ms | SQLite vector similarity search |",
        f"| **Mean Generation Latency** | {summary.generation_latency_mean_ms} ms | Synthesis step |",
        f"| **Cold Start Latency** | {summary.cold_start_latency_ms} ms | Initial model & index query |",
        f"| **Warmed-Up Mean Latency** | {summary.warmed_up_latency_mean_ms} ms | Steady-state average |",
        "",
        "## 3. Per-Category Quality Breakdown",
        "",
        "| Category | Cases | Pass Rate | Hit Rate | Recall@k | Fact Score | Mean Latency |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for cat, stats in summary.per_category.items():
        lines.append(
            f"| `{cat}` | {int(stats['count'])} | {stats['pass_rate'] * 100:.1f}% | "
            f"{stats['hit_rate'] * 100:.1f}% | {stats['recall_at_k'] * 100:.1f}% | "
            f"{stats['fact_score'] * 100:.1f}% | {stats['mean_latency_ms']} ms |"
        )

    if comparison:
        lines.extend([
            "",
            "## 4. Configuration Comparison (Retrieval Top-K)",
            "",
            "| Configuration | Hit Rate | Recall@k | Precision@k | MRR | Overall Pass | Retrieval Latency | p95 Latency |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])
        for entry in comparison.entries:
            lines.append(
                f"| `{entry.config_name}` | {entry.hit_rate * 100:.1f}% | "
                f"{entry.mean_recall_at_k * 100:.1f}% | {entry.mean_precision_at_k * 100:.1f}% | "
                f"{entry.mean_mrr:.3f} | {entry.overall_pass_rate * 100:.1f}% | "
                f"{entry.retrieval_latency_mean_ms} ms | {entry.latency_p95_ms} ms |"
            )
        lines.extend([
            "",
            f"> **Analysis:** {comparison.notes}",
        ])

    failures = [c for c in summary.cases if not c.passed]
    lines.extend([
        "",
        "## 5. Failure Analysis",
        "",
    ])
    if not failures:
        lines.append("All evaluation cases passed quality, citation, refusal, and security isolation thresholds.")
    else:
        lines.append(f"Found {len(failures)} case(s) requiring attention:")
        for f in failures:
            lines.append(f"- **[{f.case_id}]** `{f.category}`: *\"{f.question}\"*")
            for reason in f.failure_reasons:
                lines.append(f"  - Failure: {reason}")

    lines.append("")
    return "\n".join(lines)


def generate_reports(
    summary: EvaluationSummary,
    comparison: BenchmarkComparisonReport | None = None,
    output_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Saves both JSON and Markdown evaluation reports."""
    target_dir = output_dir or (Path(__file__).resolve().parent / "reports")
    target_dir.mkdir(parents=True, exist_ok=True)

    json_path = target_dir / "eval_report.json"
    md_path = target_dir / "eval_report.md"

    # Save JSON report
    data = summary.model_dump()
    if comparison:
        data["comparison"] = comparison.model_dump()
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # Save Markdown report
    md_content = generate_markdown_report(summary, comparison)
    md_path.write_text(md_content, encoding="utf-8")

    return json_path, md_path
