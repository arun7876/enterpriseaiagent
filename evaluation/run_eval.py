import argparse
import sys
import tempfile
from pathlib import Path

from evaluation.benchmark import run_retrieval_comparison
from evaluation.dataset import load_eval_dataset
from evaluation.reporter import generate_reports
from evaluation.runner import EvaluationRunner


def main() -> None:
    parser = argparse.ArgumentParser(description="Enterprise AI Research Agent RAG Evaluation System")
    parser.add_argument(
        "--mode",
        choices=["deterministic", "model"],
        default="deterministic",
        help="Evaluation mode: deterministic (offline, fast, CI friendly) or model (local Ollama)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Retrieval top-k parameter (default: 5)",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run comparative benchmark across top-k values (3, 5, 8)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="evaluation/reports",
        help="Directory to save evaluation reports",
    )

    args = parser.parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("ENTERPRISE AI RESEARCH AGENT — RAG EVALUATION & BENCHMARKING")
    print(f"Mode: {args.mode} | Top-K: {args.top_k} | Output: {output_dir}")
    print("=" * 70)

    with tempfile.TemporaryDirectory(prefix="rag-eval-") as temp_dir:
        temp_index = Path(temp_dir) / "eval_vector_index.sqlite3"
        print(f"Initializing evaluation runner with isolated index: {temp_index.name}...")

        dataset = load_eval_dataset()
        print(f"Loaded {len(dataset.cases)} evaluation test cases from eval_dataset.json.")

        runner = EvaluationRunner(
            index_path=temp_index,
            mode=args.mode,
            top_k=args.top_k,
        )

        print("\nExecuting evaluation test cases...")
        summary = runner.run_suite(dataset)

        comparison_report = None
        if args.compare:
            print("\nRunning comparative benchmark across retrieval top-k values (3, 5, 8)...")
            comparison_report = run_retrieval_comparison(
                index_path=temp_index,
                k_values=(3, 5, 8),
                dataset=dataset,
                mode=args.mode,
            )

        json_path, md_path = generate_reports(
            summary=summary,
            comparison=comparison_report,
            output_dir=output_dir,
        )

        print("\n" + "=" * 70)
        print("EVALUATION RESULTS SUMMARY")
        print("=" * 70)
        print(f"Cases Evaluated:           {summary.dataset_size}")
        print(f"Overall Pass Rate:         {summary.overall_pass_rate * 100:.1f}%")
        print(f"Retrieval Hit Rate:        {summary.hit_rate * 100:.1f}%")
        print(f"Mean Recall@{args.top_k}:            {summary.mean_recall_at_k * 100:.1f}%")
        print(f"Mean Precision@{args.top_k}:         {summary.mean_precision_at_k * 100:.1f}%")
        print(f"Mean Reciprocal Rank (MRR): {summary.mean_mrr:.3f}")
        print(f"Factual Coverage:          {summary.mean_fact_score * 100:.1f}%")
        print(f"Refusal Accuracy:          {summary.refusal_accuracy * 100:.1f}%")
        print(f"Citation Precision:        {summary.citation_precision * 100:.1f}%")
        print(f"Security Pass Rate:        {summary.security_pass_rate * 100:.1f}%")
        print("-" * 70)
        print(f"Median Latency (p50):      {summary.latency_p50_ms:.1f} ms")
        print(f"95th Percentile (p95):     {summary.latency_p95_ms:.1f} ms")
        print(f"Mean Retrieval Latency:    {summary.retrieval_latency_mean_ms:.1f} ms")
        print(f"Mean Generation Latency:   {summary.generation_latency_mean_ms:.1f} ms")
        print("=" * 70)
        print(f"Saved JSON Report: {json_path}")
        print(f"Saved Markdown Report: {md_path}")
        print("=" * 70)


if __name__ == "__main__":
    main()
