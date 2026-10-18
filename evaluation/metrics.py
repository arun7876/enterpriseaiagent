import re
from typing import Any, Sequence

REFUSAL_PHRASES = (
    "the indexed documents do not provide enough evidence",
    "does not provide enough evidence",
    "insufficient evidence",
    "not enough evidence",
    "cannot be found",
    "not mentioned",
    "not provided",
    "no evidence",
    "unable to find",
    "not contained in",
)


def hit_rate(
    retrieved_sources: Sequence[str],
    relevant_sources: Sequence[str],
    k: int | None = None,
) -> float:
    """Returns 1.0 if at least one relevant source appears in top-k, else 0.0."""
    if not relevant_sources:
        return 1.0
    candidates = list(retrieved_sources[:k] if k is not None else retrieved_sources)
    target_set = set(relevant_sources)
    return 1.0 if any(source in target_set for source in candidates) else 0.0


def recall_at_k(
    retrieved_sources: Sequence[str],
    relevant_sources: Sequence[str],
    k: int,
) -> float:
    """Fraction of relevant sources retrieved in the top-k results."""
    if not relevant_sources:
        return 1.0
    if k <= 0:
        return 0.0
    candidates = set(retrieved_sources[:k])
    targets = set(relevant_sources)
    hits = len(candidates.intersection(targets))
    return float(hits / len(targets))


def precision_at_k(
    retrieved_sources: Sequence[str],
    relevant_sources: Sequence[str],
    k: int,
) -> float:
    """Fraction of the top-k retrieved sources that are relevant."""
    if k <= 0:
        return 0.0
    candidates = list(retrieved_sources[:k])
    if not candidates:
        return 0.0
    targets = set(relevant_sources)
    hits = sum(1 for source in candidates if source in targets)
    return float(hits / len(candidates))


def reciprocal_rank(
    retrieved_sources: Sequence[str],
    relevant_sources: Sequence[str],
) -> float:
    """1 / rank of the first relevant source retrieved, or 0.0 if none found."""
    if not relevant_sources:
        return 1.0
    targets = set(relevant_sources)
    for index, source in enumerate(retrieved_sources, start=1):
        if source in targets:
            return 1.0 / index
    return 0.0


def fact_presence_score(
    answer: str,
    essential_facts: Sequence[str],
) -> float:
    """Fraction of essential fact strings or regexes detected in the answer."""
    if not essential_facts:
        return 1.0
    lowered_answer = answer.casefold()
    found = 0
    for fact in essential_facts:
        lowered_fact = fact.casefold()
        if lowered_fact in lowered_answer or re.search(re.escape(lowered_fact), lowered_answer):
            found += 1
    return float(found / len(essential_facts))


def is_refusal_answer(answer: str) -> bool:
    """Checks whether the answer signals refusal or insufficient evidence."""
    lowered = answer.casefold()
    return any(phrase in lowered for phrase in REFUSAL_PHRASES)


def refusal_accuracy(
    answer: str,
    expected_behavior: str,
    citation_count: int = 0,
) -> bool:
    """Verifies that ungrounded/unsupported questions trigger clean refusal with 0 citations."""
    is_refusal = is_refusal_answer(answer)
    if expected_behavior in {"refuse", "deny_access"}:
        return is_refusal and citation_count == 0
    return not is_refusal


def citation_precision(
    cited_sources: Sequence[str],
    relevant_sources: Sequence[str],
    expected_behavior: str = "answer",
) -> float:
    """Proportion of cited sources that actually match labeled relevant sources."""
    if expected_behavior in {"refuse", "deny_access"}:
        return 1.0 if len(cited_sources) == 0 else 0.0
    if not cited_sources:
        return 0.0
    targets = set(relevant_sources)
    valid_citations = sum(1 for source in cited_sources if source in targets)
    return float(valid_citations / len(cited_sources))


def citation_coverage(
    cited_sources: Sequence[str],
    expected_behavior: str,
) -> bool:
    """Checks whether supported answers provide at least one citation and refusals have zero."""
    if expected_behavior in {"refuse", "deny_access"}:
        return len(cited_sources) == 0
    return len(cited_sources) > 0


def security_isolation_passed(
    retrieved_sources: Sequence[str],
    cited_sources: Sequence[str],
    forbidden_facts: Sequence[str],
    answer: str,
    unauthorized_sources: Sequence[str],
) -> bool:
    """Confirms no private documents are retrieved or cited, and no forbidden facts are leaked."""
    unauthorized_set = set(unauthorized_sources)
    if any(source in unauthorized_set for source in retrieved_sources):
        return False
    if any(source in unauthorized_set for source in cited_sources):
        return False
    lowered_answer = answer.casefold()
    for forbidden in forbidden_facts:
        if forbidden.casefold() in lowered_answer:
            return False
    return True
