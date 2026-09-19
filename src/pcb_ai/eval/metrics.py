"""Evaluation metrics (Phase 19).

Metrics that require information this harness does not currently have
(per-case labeled "relevant retrieval" ground truth for retrieval
precision/recall, and real API pricing for cost) are explicitly reported
as `None`/a `NOT_COMPUTABLE` note rather than fabricated -- see
`IMPORTANT: RESEARCH INTEGRITY` in the architecture spec.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pcb_ai.schemas.diagnosis import ViolationDiagnosis
from pcb_ai.schemas.evaluation import EvaluationRecord


def _word_overlap_score(candidate: str, reference: str) -> float:
    """Heuristic text-similarity proxy (Jaccard word overlap), NOT a
    substitute for human judgement or a proper NLG metric (e.g. ROUGE/
    BERTScore) -- used only because no such library is currently a project
    dependency. Documented as a heuristic in EVALUATION.md."""
    cand_words = {w.lower().strip(".,;:()") for w in candidate.split() if len(w) > 2}
    ref_words = {w.lower().strip(".,;:()") for w in reference.split() if len(w) > 2}
    if not ref_words:
        return 0.0
    intersection = cand_words & ref_words
    union = cand_words | ref_words
    return len(intersection) / len(union) if union else 0.0


@dataclass
class RecordMetrics:
    violation_id: str
    condition: str
    classification_correct: bool
    severity_agreement: bool
    human_review_agreement: bool
    root_cause_overlap: float
    recommendation_overlap: float
    evidence_grounded: bool
    hallucination_flag: bool
    unsupported_claim_count: int
    evidence_word_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: Optional[float]


def score_record(
    diagnosis: ViolationDiagnosis,
    record: EvaluationRecord,
    condition: str,
    metadata: dict,
    latency_ms: Optional[float] = None,
) -> RecordMetrics:
    predicted_type = diagnosis.classification.type.lower().replace(" ", "_")
    expected_type = record.violation_type.lower().replace(" ", "_")
    classification_correct = (
        predicted_type == expected_type or expected_type in predicted_type or predicted_type in expected_type
    )

    reported_severity = (diagnosis.deterministic_severity or diagnosis.classification.severity).value
    severity_agreement = reported_severity == record.severity_ground_truth.lower()

    human_review_agreement = diagnosis.requires_human_review == record.requires_human_review

    root_cause_overlap = _word_overlap_score(diagnosis.root_cause.explanation, record.expert_root_cause)
    recommendation_overlap = _word_overlap_score(diagnosis.recommended_fix.description, record.expert_recommendation)

    evidence_grounded = bool(diagnosis.validation_passed)
    hallucination_flag = (diagnosis.validation_passed is False) or diagnosis.insufficient_evidence
    unsupported_claim_count = len(diagnosis.validation_errors)

    token_usage = metadata.get("token_usage", {})
    return RecordMetrics(
        violation_id=diagnosis.violation_id,
        condition=condition,
        classification_correct=classification_correct,
        severity_agreement=severity_agreement,
        human_review_agreement=human_review_agreement,
        root_cause_overlap=root_cause_overlap,
        recommendation_overlap=recommendation_overlap,
        evidence_grounded=evidence_grounded,
        hallucination_flag=hallucination_flag,
        unsupported_claim_count=unsupported_claim_count,
        evidence_word_count=metadata.get("evidence_word_count", 0),
        prompt_tokens=token_usage.get("prompt_tokens", 0),
        completion_tokens=token_usage.get("completion_tokens", 0),
        total_tokens=token_usage.get("total_tokens", 0),
        latency_ms=latency_ms,
    )


@dataclass
class AggregateMetrics:
    condition: str
    n: int
    classification_accuracy: float
    severity_agreement_rate: float
    human_review_agreement_rate: float
    mean_root_cause_overlap: float
    mean_recommendation_overlap: float
    evidence_grounding_rate: float
    hallucination_rate: float
    mean_unsupported_claims: float
    mean_evidence_word_count: float
    mean_total_tokens: float
    mean_latency_ms: Optional[float]
    retrieval_precision: str = "NOT_COMPUTABLE: no per-case relevant-document ground truth in dataset"
    retrieval_recall: str = "NOT_COMPUTABLE: no per-case relevant-document ground truth in dataset"
    cost: str = "NOT_COMPUTABLE: no pricing configured for the evaluated model"


def aggregate(records: list[RecordMetrics], condition: str) -> AggregateMetrics:
    n = len(records)
    if n == 0:
        return AggregateMetrics(
            condition=condition,
            n=0,
            classification_accuracy=0.0,
            severity_agreement_rate=0.0,
            human_review_agreement_rate=0.0,
            mean_root_cause_overlap=0.0,
            mean_recommendation_overlap=0.0,
            evidence_grounding_rate=0.0,
            hallucination_rate=0.0,
            mean_unsupported_claims=0.0,
            mean_evidence_word_count=0.0,
            mean_total_tokens=0.0,
            mean_latency_ms=None,
        )
    latencies = [r.latency_ms for r in records if r.latency_ms is not None]
    return AggregateMetrics(
        condition=condition,
        n=n,
        classification_accuracy=sum(r.classification_correct for r in records) / n,
        severity_agreement_rate=sum(r.severity_agreement for r in records) / n,
        human_review_agreement_rate=sum(r.human_review_agreement for r in records) / n,
        mean_root_cause_overlap=sum(r.root_cause_overlap for r in records) / n,
        mean_recommendation_overlap=sum(r.recommendation_overlap for r in records) / n,
        evidence_grounding_rate=sum(r.evidence_grounded for r in records) / n,
        hallucination_rate=sum(r.hallucination_flag for r in records) / n,
        mean_unsupported_claims=sum(r.unsupported_claim_count for r in records) / n,
        mean_evidence_word_count=sum(r.evidence_word_count for r in records) / n,
        mean_total_tokens=sum(r.total_tokens for r in records) / n,
        mean_latency_ms=(sum(latencies) / len(latencies)) if latencies else None,
    )
