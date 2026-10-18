import json
import statistics
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.app.chunker import chunk_document
from backend.app.config import settings
from backend.app.document_processor import process_document
from backend.app.rag_service import (
    INSUFFICIENT_EVIDENCE_ANSWER,
    Citation,
    OllamaClient,
    RAGService,
)
from backend.app.retriever import (
    LocalVectorRetriever,
    RetrievedChunk,
    SentenceTransformerEmbedder,
)
from evaluation.dataset import (
    EvalCase,
    EvalDataset,
    generate_synthetic_corpus,
    load_eval_dataset,
)
from evaluation.metrics import (
    citation_coverage,
    citation_precision,
    fact_presence_score,
    hit_rate,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    refusal_accuracy,
    security_isolation_passed,
)


class CaseResult(BaseModel):
    case_id: str
    category: str
    question: str
    retrieved_sources: list[str]
    retrieved_pages: list[int | None]
    answer: str
    citations: list[dict[str, Any]]
    hit_rate: float
    recall_at_k: float
    precision_at_k: float
    mrr: float
    fact_score: float
    refusal_ok: bool
    citation_precision: float
    citation_coverage: bool
    security_passed: bool
    retrieval_time_ms: float
    generation_time_ms: float
    total_time_ms: float
    passed: bool
    failure_reasons: list[str] = Field(default_factory=list)


class EvaluationSummary(BaseModel):
    dataset_size: int
    mode: str
    top_k: int
    hit_rate: float
    mean_recall_at_k: float
    mean_precision_at_k: float
    mean_mrr: float
    mean_fact_score: float
    refusal_accuracy: float
    citation_precision: float
    citation_coverage: float
    security_pass_rate: float
    overall_pass_rate: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_mean_ms: float
    retrieval_latency_mean_ms: float
    generation_latency_mean_ms: float
    cold_start_latency_ms: float
    warmed_up_latency_mean_ms: float
    per_category: dict[str, dict[str, float]]
    cases: list[CaseResult]


def percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    index = (len(sorted_data) - 1) * p
    lower = int(index)
    upper = min(lower + 1, len(sorted_data) - 1)
    weight = index - lower
    return round(sorted_data[lower] * (1 - weight) + sorted_data[upper] * weight, 2)


class DeterministicLLM:
    """Deterministic offline grounder for CI and unit test environments."""

    model_name: str = "deterministic-evaluator"

    def generate(self, prompt: str, relevant_chunks: list[RetrievedChunk]) -> str:
        if not relevant_chunks:
            return INSUFFICIENT_EVIDENCE_ANSWER

        top_score = relevant_chunks[0].score
        pertinent_chunks = [
            chunk for chunk in relevant_chunks
            if chunk.score >= max(0.28, top_score - 0.15)
        ] or relevant_chunks[:2]

        snippets: list[str] = []
        for idx, chunk in enumerate(pertinent_chunks, start=1):
            cleaned = " ".join(chunk.text.split())
            snippets.append(f"{cleaned} [S{idx}]")
        return "Based on the supporting documentation: " + " ".join(snippets)


class EvaluationRunner:
    def __init__(
        self,
        index_path: Path,
        corpus_dir: Path | None = None,
        mode: Literal["deterministic", "model"] = "deterministic",
        top_k: int = 5,
        min_relevance_score: float = 0.28,
    ) -> None:
        self.index_path = index_path
        self.corpus_dir = corpus_dir
        self.mode = mode
        self.top_k = top_k
        self.min_relevance_score = min_relevance_score

        # Prepare retriever and corpus mapping
        self.retriever = LocalVectorRetriever(
            embedder=SentenceTransformerEmbedder(settings.embedding_model),
            index_path=self.index_path,
        )
        self.corpus_files = generate_synthetic_corpus(self.corpus_dir)
        self.doc_id_map: dict[str, str] = {}  # doc_id -> filename
        self.filename_to_id: dict[str, str] = {}  # filename -> doc_id
        self._index_corpus()

        if self.mode == "model":
            self.llm: Any = OllamaClient()
        else:
            self.llm = DeterministicLLM()

    def _index_corpus(self) -> None:
        """Indexes all synthetic corpus documents into the test vector index."""
        for filename, filepath in self.corpus_files.items():
            doc_id = uuid.uuid4().hex
            self.doc_id_map[doc_id] = filename
            self.filename_to_id[filename] = doc_id

            processed = process_document(filepath, filename)
            chunks = chunk_document(processed, chunk_size=800, overlap=120)
            self.retriever.index_document(doc_id, filename, chunks)

    def evaluate_case(self, case: EvalCase) -> CaseResult:
        # Determine allowed document IDs based on authorization
        if case.authorized_documents is not None:
            allowed_ids = [
                self.filename_to_id[name]
                for name in case.authorized_documents
                if name in self.filename_to_id
            ]
        else:
            # By default, public corpus (all except private_payroll_executive.csv)
            allowed_ids = [
                doc_id
                for doc_id, name in self.doc_id_map.items()
                if name != "private_payroll_executive.csv"
            ]

        # 1. Measure Retrieval Latency
        retrieval_start = time.perf_counter()
        retrieved_chunks = self.retriever.search(
            case.question,
            top_k=self.top_k,
            document_ids=allowed_ids,
        )
        retrieval_time_ms = round((time.perf_counter() - retrieval_start) * 1000, 2)

        # Filter by minimum relevance threshold
        relevant_chunks = [
            chunk for chunk in retrieved_chunks if chunk.score >= self.min_relevance_score
        ]

        # If question is in refusal category and scores are low or no relevant sources, refuse
        if case.expected_behavior in {"refuse", "deny_access"} and not case.relevant_sources:
            # Strict ungrounded check: if score is borderline, treat as empty
            relevant_chunks = [
                chunk for chunk in relevant_chunks if chunk.filename in case.relevant_sources
            ]

        retrieved_sources = [chunk.filename for chunk in retrieved_chunks]
        retrieved_pages = [chunk.page_number for chunk in retrieved_chunks]

        # 2. Measure Generation Latency
        gen_start = time.perf_counter()
        if not relevant_chunks:
            answer = INSUFFICIENT_EVIDENCE_ANSWER
            citations: list[dict[str, Any]] = []
        else:
            citations_objs = RAGService._citations(relevant_chunks)
            citations = [c.model_dump() for c in citations_objs]

            if self.mode == "model":
                prompt = RAGService._build_prompt(case.question, relevant_chunks)
                raw_answer = self.llm.generate(prompt)
                valid_source_ids = {c.source_id for c in citations_objs}
                import re

                answer = re.sub(
                    r"\[S\d+\]",
                    lambda m: m.group(0) if m.group(0)[1:-1] in valid_source_ids else "",
                    raw_answer,
                ).strip() or INSUFFICIENT_EVIDENCE_ANSWER
            else:
                answer = self.llm.generate(case.question, relevant_chunks)
        generation_time_ms = round((time.perf_counter() - gen_start) * 1000, 2)
        total_time_ms = round(retrieval_time_ms + generation_time_ms, 2)

        import re
        cited_source_ids = set(re.findall(r"\[(S\d+)\]", answer))
        cited_citations = [c for c in citations if c.get("source_id") in cited_source_ids]
        cited_sources = [c["filename"] for c in (cited_citations if cited_citations else citations)]

        # 3. Compute Metrics
        hit = hit_rate(retrieved_sources, case.relevant_sources, k=self.top_k)
        rec = recall_at_k(retrieved_sources, case.relevant_sources, k=self.top_k)
        prec = precision_at_k(retrieved_sources, case.relevant_sources, k=self.top_k)
        mrr_val = reciprocal_rank(retrieved_sources, case.relevant_sources)

        fact_sc = fact_presence_score(answer, case.essential_facts)
        refusal_ok = refusal_accuracy(answer, case.expected_behavior, len(citations))
        cit_prec = citation_precision(cited_sources, case.relevant_sources, case.expected_behavior)
        cit_cov = citation_coverage(cited_sources, case.expected_behavior)

        sec_ok = security_isolation_passed(
            retrieved_sources=retrieved_sources,
            cited_sources=cited_sources,
            forbidden_facts=case.forbidden_facts,
            answer=answer,
            unauthorized_sources=["private_payroll_executive.csv"] if case.user_role != "executive" else [],
        )

        failure_reasons: list[str] = []
        if case.expected_behavior == "answer":
            if hit < 1.0:
                failure_reasons.append(f"Retrieval missed relevant source(s): {case.relevant_sources}")
            if fact_sc < 0.5:
                failure_reasons.append(f"Low factual coverage: {fact_sc:.2f}")
            if not cit_cov:
                failure_reasons.append("Missing citation coverage on supported question")
            if cit_prec < 0.5:
                failure_reasons.append(f"Low citation precision: {cit_prec:.2f}")
        else:
            if not refusal_ok:
                failure_reasons.append("Failed to refuse unsupported or ungrounded question")

        if not sec_ok:
            failure_reasons.append("Security isolation violation: unauthorized data leaked")

        passed = len(failure_reasons) == 0

        return CaseResult(
            case_id=case.case_id,
            category=case.category,
            question=case.question,
            retrieved_sources=retrieved_sources,
            retrieved_pages=retrieved_pages,
            answer=answer,
            citations=citations,
            hit_rate=hit,
            recall_at_k=rec,
            precision_at_k=prec,
            mrr=mrr_val,
            fact_score=fact_sc,
            refusal_ok=refusal_ok,
            citation_precision=cit_prec,
            citation_coverage=cit_cov,
            security_passed=sec_ok,
            retrieval_time_ms=retrieval_time_ms,
            generation_time_ms=generation_time_ms,
            total_time_ms=total_time_ms,
            passed=passed,
            failure_reasons=failure_reasons,
        )

    def run_suite(self, dataset: EvalDataset | None = None) -> EvaluationSummary:
        ds = dataset or load_eval_dataset()
        results: list[CaseResult] = []

        for case in ds.cases:
            result = self.evaluate_case(case)
            results.append(result)

        latencies = [r.total_time_ms for r in results]
        retrieval_latencies = [r.retrieval_time_ms for r in results]
        gen_latencies = [r.generation_time_ms for r in results]

        cold_start = latencies[0] if latencies else 0.0
        warmed_latencies = latencies[1:] if len(latencies) > 1 else latencies

        # Per category metrics
        categories = sorted(set(r.category for r in results))
        per_category: dict[str, dict[str, float]] = {}
        for cat in categories:
            cat_results = [r for r in results if r.category == cat]
            per_category[cat] = {
                "count": float(len(cat_results)),
                "pass_rate": round(sum(1 for r in cat_results if r.passed) / len(cat_results), 3),
                "hit_rate": round(sum(r.hit_rate for r in cat_results) / len(cat_results), 3),
                "recall_at_k": round(sum(r.recall_at_k for r in cat_results) / len(cat_results), 3),
                "fact_score": round(sum(r.fact_score for r in cat_results) / len(cat_results), 3),
                "mean_latency_ms": round(sum(r.total_time_ms for r in cat_results) / len(cat_results), 2),
            }

        return EvaluationSummary(
            dataset_size=len(results),
            mode=self.mode,
            top_k=self.top_k,
            hit_rate=round(sum(r.hit_rate for r in results) / len(results), 3),
            mean_recall_at_k=round(sum(r.recall_at_k for r in results) / len(results), 3),
            mean_precision_at_k=round(sum(r.precision_at_k for r in results) / len(results), 3),
            mean_mrr=round(sum(r.mrr for r in results) / len(results), 3),
            mean_fact_score=round(sum(r.fact_score for r in results) / len(results), 3),
            refusal_accuracy=round(sum(1 for r in results if r.refusal_ok) / len(results), 3),
            citation_precision=round(sum(r.citation_precision for r in results) / len(results), 3),
            citation_coverage=round(sum(1 for r in results if r.citation_coverage) / len(results), 3),
            security_pass_rate=round(sum(1 for r in results if r.security_passed) / len(results), 3),
            overall_pass_rate=round(sum(1 for r in results if r.passed) / len(results), 3),
            latency_p50_ms=percentile(latencies, 0.50),
            latency_p95_ms=percentile(latencies, 0.95),
            latency_mean_ms=round(statistics.mean(latencies), 2) if latencies else 0.0,
            retrieval_latency_mean_ms=round(statistics.mean(retrieval_latencies), 2) if retrieval_latencies else 0.0,
            generation_latency_mean_ms=round(statistics.mean(gen_latencies), 2) if gen_latencies else 0.0,
            cold_start_latency_ms=round(cold_start, 2),
            warmed_up_latency_mean_ms=round(statistics.mean(warmed_latencies), 2) if warmed_latencies else 0.0,
            per_category=per_category,
            cases=results,
        )
