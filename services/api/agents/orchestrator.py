"""Explicit, bounded multi-agent investigation pipeline.

Order: load incident -> validate source data -> deterministic evidence
preparation -> Sensor Agent -> Knowledge Agent -> Investigation Agent -> Critic
Agent -> reference validation -> one bounded revision -> final report.

There are no unrestricted agent loops: every model call has a timeout and a
limited retry policy, and the revision count is capped.
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from services.api.agents import (
    critic_agent,
    investigation_agent,
    knowledge_agent,
    sensor_agent,
)
from services.api.agents.base import AgentSpec
from services.api.agents.runtime import AdkRuntime, InvestigationProviderError
from services.api.core import config
from services.api.schemas.hypothesis import Hypothesis
from services.api.schemas.investigation import (
    REPORT_DISCLAIMER,
    CriticReview,
    RecommendedAction,
)
from services.api.tools.anomaly_tools import (
    get_anomaly_analysis,
    get_baseline_statistics,
)
from services.api.tools.evidence_tools import (
    build_deterministic_evidence,
    evidence_catalog,
    validate_evidence_ids,
)
from services.api.tools.incident_tools import (
    get_incident_context,
    get_incident_measurements,
)
from services.api.tools.knowledge_tools import retrieve_knowledge, get_passage
from services.api.tools.grounding import normalize_analysis, text_issues, critic_requires_revision, validate_sensor_snapshot

logger = logging.getLogger(__name__)

MAX_REVISIONS = 1
MAX_RECOMMENDED_ACTIONS = 6


class InvestigationError(Exception):
    """Raised when an investigation cannot be completed."""


class InvestigationDisabledError(InvestigationError):
    """Raised when AI investigation is disabled by configuration."""


class ProgressReporter(Protocol):
    def stage(self, stage: str, message: str | None = None) -> None: ...

    def agent(
        self,
        name: str,
        status: str,
        summary: str | None = None,
        evidence_count: int | None = None,
    ) -> None: ...

    def evidence(self, records: list[dict[str, Any]]) -> None: ...

    def activity(self) -> list[dict[str, Any]]: ...


@dataclass
class InvestigationResult:
    report: dict[str, Any]
    evidence: list[dict[str, Any]]


@dataclass
class PreparedContext:
    """A pre-built, deterministic reasoning context.

    Normal investigations build this from the dataset tools; counterfactual
    investigations build a *restricted* version (excluded measurements already
    removed) so the agents never see the excluded data.
    """

    incident_context: dict[str, Any]
    measurements: dict[str, Any]
    anomaly: dict[str, Any]
    baselines: dict[str, Any]
    passages: list[dict[str, Any]]
    evidence_records: list[dict[str, Any]]
    counterfactual: dict[str, Any] | None = None


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _knowledge_query(anomaly: dict[str, Any]) -> str:
    tokens: list[str] = []
    for feature in anomaly.get("anomalous_features", []):
        label = feature.get("label") or feature.get("feature") or ""
        direction = feature.get("direction") or ""
        tokens.append(str(label))
        if direction:
            tokens.append(str(direction))
    tokens.append("troubleshooting maintenance inspection")
    return " ".join(tokens)


def _revision_feedback(critic: dict[str, Any], rejected: list[str]) -> str:
    parts: list[str] = []
    for issue in critic.get("issues_found", []) or []:
        parts.append(f"- issue: {issue}")
    for claim in critic.get("unsupported_claims", []) or []:
        parts.append(f"- unsupported claim: {claim}")
    for item in critic.get("citation_issues", []) or []:
        parts.append(f"- citation problem: {item}")
    for key in ("contradictions", "missing_evidence", "deterministic_findings"):
        parts.extend(f"- {key}: {item}" for item in critic.get(key, []) or [])
    if rejected:
        parts.append(
            "- invalid evidence IDs that must be removed or replaced: "
            + ", ".join(sorted(set(rejected)))
        )
    return (
        "\n".join(parts)
        if parts
        else "- Strengthen evidence linkage and remove unsupported claims."
    )


class Orchestrator:
    def __init__(
        self,
        runtime: AdkRuntime,
        incident_service,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        max_hypotheses: int | None = None,
    ) -> None:
        self.runtime = runtime
        self.incident_service = incident_service
        self.timeout = float(
            timeout_seconds
            if timeout_seconds is not None
            else config.settings.investigation_timeout_seconds
        )
        self.max_retries = max(0, min(5, int(
            max_retries
            if max_retries is not None
            else config.settings.investigation_max_retries
        )))
        self.max_hypotheses = int(
            max_hypotheses
            if max_hypotheses is not None
            else config.settings.investigation_max_hypotheses
        )

    # -- agent execution -------------------------------------------------

    async def _run_agent(
        self, spec: AgentSpec, context: dict[str, Any], image_parts=None
    ) -> dict[str, Any]:
        prompt = spec.build_prompt(context)
        attempts = self.max_retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                output = await asyncio.wait_for(
                    self.runtime.run(spec, prompt, image_parts=image_parts) if image_parts is not None else self.runtime.run(spec, prompt), timeout=self.timeout
                )
                return spec.output_schema.model_validate(output).model_dump()
            except (asyncio.TimeoutError, InvestigationProviderError) as exc:
                last_error = (InvestigationProviderError(f'Timed out after {self.timeout:g} seconds')
                              if isinstance(exc, asyncio.TimeoutError) else exc)
                logger.warning(
                    "Agent %s attempt %d/%d failed category=%s",
                    spec.name,
                    attempt + 1,
                    attempts,
                    last_error.category,
                )
                retryable = isinstance(exc, asyncio.TimeoutError) or exc.retryable
                if not retryable:
                    break
                if attempt < attempts - 1:
                    provider_delay = exc.retry_after_seconds if isinstance(exc, InvestigationProviderError) else None
                    await asyncio.sleep(max(min(5 * 2**attempt, 30), provider_delay or 0) + random.uniform(0, 1))
            except Exception as exc:  # validation / unexpected
                last_error = InvestigationProviderError(f'Invalid structured output ({type(exc).__name__}); no report can be verified.')
                logger.warning("Agent %s validation error: %s", spec.name, type(exc).__name__)
                break
        raise InvestigationError(f"{spec.name} failed: {last_error}")

    # -- pipeline --------------------------------------------------------

    async def run(
        self,
        investigation_id: str,
        incident_id: str,
        reporter: ProgressReporter,
        prepared: PreparedContext | None = None,
    ) -> InvestigationResult:
        counterfactual: dict[str, Any] | None = None
        if prepared is None:
            reporter.stage("collecting_evidence", "Loading incident and source data")
            incident = self.incident_service.get_incident(incident_id)
            measurements = get_incident_measurements(incident_id)
            anomaly = get_anomaly_analysis(incident_id)
            baselines = get_baseline_statistics(incident["machine_type"])
            validate_sensor_snapshot(measurements, anomaly)

            passages = retrieve_knowledge(
                _knowledge_query(anomaly), top_k=config.KNOWLEDGE_TOP_K
            )
            for passage in passages:
                source = get_passage(passage['document_id'], passage['section_id'])
                if source is None or any(passage.get(k) != source.get(k) for k in
                                         ('text', 'document_title', 'heading')):
                    raise InvestigationError("Retrieved passage failed corpus provenance validation")
            created_at = _utcnow_iso()
            evidence_records = build_deterministic_evidence(
                investigation_id=investigation_id,
                incident=incident,
                anomaly=anomaly,
                passages=passages,
                created_at=created_at,
            )
            catalog = evidence_catalog(evidence_records)
            reporter.evidence(evidence_records)

            incident_context = get_incident_context(incident_id)
            incident_context["severity"] = anomaly["severity"]
        else:
            # Counterfactual: the restricted context was prepared upstream.
            incident_context = prepared.incident_context
            measurements = prepared.measurements
            anomaly = prepared.anomaly
            baselines = prepared.baselines
            passages = prepared.passages
            evidence_records = prepared.evidence_records
            catalog = evidence_catalog(evidence_records)
            counterfactual = prepared.counterfactual
            reporter.evidence(evidence_records)

        # Bind by document/section identity, not by list position (counterfactual
        # exclusions leave gaps in the original immutable IDs).
        manual_records = [r for r in evidence_records if r['evidence_type'] == 'manual_passage']
        by_source = {(r['payload']['document_id'], r['payload']['section_id']): r
                     for r in manual_records}
        passages = [{**p, 'evidence_id': by_source[(p['document_id'], p['section_id'])]['evidence_id']}
                    for p in passages if (p['document_id'], p['section_id']) in by_source]
        grounding_findings: list[str] = []
        base_context: dict[str, Any] = {
            "incident": incident_context,
            "measurements": measurements,
            "anomaly": anomaly,
            "baselines": baselines,
            "passages": passages,
            "evidence": evidence_records,
            "max_hypotheses": self.max_hypotheses,
        }

        reporter.stage("analyzing_measurements", "Running Sensor Analysis Agent")
        reporter.agent("sensor_agent", "running")
        sensor_analysis = await self._run_agent(sensor_agent.SPEC, base_context)
        sensor_analysis, issues = normalize_analysis(sensor_analysis, catalog, 'sensor')
        grounding_findings.extend(issues)
        reporter.agent(
            "sensor_agent",
            "completed",
            summary=sensor_analysis.get("summary"),
            evidence_count=len(
                sensor_analysis.get("referenced_evidence_ids", []) or []
            ),
        )

        reporter.stage("retrieving_knowledge", "Running Knowledge Retrieval Agent")
        reporter.agent("knowledge_agent", "running")
        knowledge_analysis = await self._run_agent(knowledge_agent.SPEC, base_context)
        knowledge_analysis, issues = normalize_analysis(knowledge_analysis, catalog, 'knowledge')
        grounding_findings.extend(issues)
        if not manual_records:
            grounding_findings.append('Missing evidence: no matching maintenance documentation retrieved.')
        reporter.agent(
            "knowledge_agent",
            "completed",
            summary=knowledge_analysis.get("summary"),
            evidence_count=len(
                knowledge_analysis.get("referenced_evidence_ids", []) or []
            ),
        )

        reporter.stage(
            "generating_hypotheses", "Running Root Cause Investigation Agent"
        )
        reporter.agent("investigation_agent", "running")
        inv_context = {
            **base_context,
            "sensor_analysis": sensor_analysis,
            "knowledge_analysis": knowledge_analysis,
        }
        draft = await self._run_agent(investigation_agent.SPEC, inv_context)
        hypotheses, rejected = self._normalize_hypotheses(draft, catalog)
        reporter.agent(
            "investigation_agent",
            "completed",
            summary=draft.get("summary"),
            evidence_count=len(hypotheses),
        )

        reporter.stage("verifying_conclusions", "Running Critic / Verification Agent")
        reporter.agent("critic_agent", "running")
        critic_context = {**base_context, "draft": draft}
        critic_output = await self._run_agent(critic_agent.SPEC, critic_context)
        self._apply_citation_reviews(hypotheses, critic_output)

        revision_count = 0
        deterministic_issues = self._draft_issues(draft, hypotheses, evidence_records)
        critic_output['deterministic_findings'] = grounding_findings + deterministic_issues
        needs_revision = critic_requires_revision(critic_output) or bool(rejected) or bool(deterministic_issues)
        if needs_revision and revision_count < MAX_REVISIONS:
            revision_count += 1
            feedback = _revision_feedback(critic_output, rejected)
            logger.info("Running bounded revision")
            revised_context = {**inv_context, "revision_feedback": feedback}
            draft = await self._run_agent(investigation_agent.SPEC, revised_context)
            hypotheses, rejected = self._normalize_hypotheses(draft, catalog)
            reporter.agent(
                "investigation_agent",
                "completed",
                summary=draft.get("summary"),
                evidence_count=len(hypotheses),
            )
            critic_output = await self._run_agent(
                critic_agent.SPEC, {**base_context, "draft": draft}
            )
            self._apply_citation_reviews(hypotheses, critic_output)
        final_issues = self._draft_issues(draft, hypotheses, evidence_records)
        critic_output['deterministic_findings'] = list(dict.fromkeys(grounding_findings + final_issues))
        critic_output['revision_required'] = critic_requires_revision(critic_output) or bool(final_issues) or bool(grounding_findings)
        if critic_output['revision_required']:
            critic_output['verification_outcome'] = 'revision required'
        # Do not publish narrative containing invented sources or quantities.
        if text_issues(draft.get('summary', ''), evidence_records):
            draft['summary'] = 'Unverified summary withheld. Review evidence and critic findings before drawing conclusions.'
        for hypothesis in hypotheses:
            linked = [catalog[i] for i in hypothesis.supporting_evidence_ids + hypothesis.contradicting_evidence_ids]
            if text_issues(hypothesis.description, linked):
                hypothesis.description = 'Unverified description withheld; further evidence is required.'
                hypothesis.assessment = 'unsupported'
            if text_issues(hypothesis.title, linked):
                hypothesis.title = 'Unverified hypothesis'
                hypothesis.assessment = 'unsupported'
            hypothesis.verification_steps = [step for step in hypothesis.verification_steps
                                             if not text_issues(step, evidence_records)]

        reporter.agent(
            "critic_agent",
            "completed",
            summary=critic_output.get("verification_outcome"),
            evidence_count=len(set(issue for key in ('issues_found', 'unsupported_claims',
                'contradictions', 'citation_issues', 'deterministic_findings')
                for issue in critic_output.get(key, []) or [])),
        )

        report = self._build_report(
            investigation_id=investigation_id,
            incident_id=incident_id,
            draft=draft,
            hypotheses=hypotheses,
            critic_output=critic_output,
            rejected=rejected,
            evidence_records=evidence_records,
            revision_count=revision_count,
            counterfactual=counterfactual,
        )
        report["agent_activity"] = reporter.activity()
        report['sensor_analysis'] = sensor_analysis
        report['knowledge_analysis'] = knowledge_analysis
        return InvestigationResult(report=report, evidence=evidence_records)

    # -- assembly --------------------------------------------------------

    @staticmethod
    def _apply_citation_reviews(hypotheses, critic_output) -> None:
        by_id = {h.hypothesis_id: h for h in hypotheses}
        reviewed = set()
        for review in critic_output.get('citation_reviews', []):
            hypothesis = by_id.get(review['hypothesis_id'])
            if hypothesis is None:
                critic_output.setdefault('citation_issues', []).append('Critic referenced an unknown hypothesis.')
                continue
            links = (hypothesis.supporting_evidence_ids if review['relationship'] == 'supporting'
                     else hypothesis.contradicting_evidence_ids)
            reviewed.add((review['hypothesis_id'], review['evidence_id'], review['relationship']))
            if review['evidence_id'] not in links:
                critic_output.setdefault('citation_issues', []).append('Critic referenced an unknown evidence relationship.')
            elif not review['valid']:
                links.remove(review['evidence_id'])
                hypothesis.assessment = 'unsupported'
                hypothesis.missing_evidence.append(review['reason'])
                critic_output.setdefault('citation_issues', []).append(
                    f"{review['hypothesis_id']} / {review['evidence_id']}: {review['reason']}")
        for hypothesis in hypotheses:
            for relationship, links in (('supporting', hypothesis.supporting_evidence_ids),
                                        ('contradicting', hypothesis.contradicting_evidence_ids)):
                for evidence_id in list(links):
                    if (hypothesis.hypothesis_id, evidence_id, relationship) not in reviewed:
                        links.remove(evidence_id)
                        hypothesis.assessment = 'unsupported'
                        issue = f'{hypothesis.hypothesis_id} / {evidence_id}: citation relationship was not reviewed.'
                        hypothesis.missing_evidence.append(issue)
                        critic_output.setdefault('citation_issues', []).append(issue)


    @staticmethod
    def _draft_issues(draft, hypotheses, records) -> list[str]:
        issues = text_issues(draft.get('summary', ''), records)
        by_id = evidence_catalog(records)
        if not hypotheses:
            issues.append('Missing evidence: no hypotheses were provided.')
        for hypothesis in hypotheses:
            if not hypothesis.supporting_evidence_ids:
                issues.append(f'{hypothesis.hypothesis_id}: no supporting evidence; assessment is unsupported.')
            linked = [by_id[i] for i in hypothesis.supporting_evidence_ids + hypothesis.contradicting_evidence_ids]
            issues.extend(text_issues(hypothesis.description, linked))
            issues.extend(text_issues(hypothesis.title, linked))
            for step in hypothesis.verification_steps:
                issues.extend(text_issues(step, records))
            overlap = set(hypothesis.supporting_evidence_ids) & set(hypothesis.contradicting_evidence_ids)
            if overlap:
                issues.append(f'{hypothesis.hypothesis_id}: same evidence marked supporting and contradicting: {sorted(overlap)}')
        return issues

    def _normalize_hypotheses(
        self, draft: dict[str, Any], catalog: dict[str, dict[str, Any]]
    ) -> tuple[list[Hypothesis], list[str]]:
        hypotheses: list[Hypothesis] = []
        rejected: list[str] = []
        raw = draft.get("hypotheses", []) or []
        for index, item in enumerate(raw[: self.max_hypotheses], start=1):
            support, reject_support = validate_evidence_ids(
                item.get("supporting_evidence_ids", []) or [], catalog
            )
            contradict, reject_contra = validate_evidence_ids(
                item.get("contradicting_evidence_ids", []) or [], catalog
            )
            rejected.extend(reject_support)
            rejected.extend(reject_contra)
            assessment = item.get("assessment", "weak")
            if assessment not in ("plausible", "weak", "unsupported"):
                assessment = "weak"
            missing = list(item.get('missing_evidence', []) or [])
            if not support:
                assessment = 'unsupported'
                missing.append('No validated supporting evidence is available.')
            if set(support) & set(contradict):
                assessment = 'unsupported'
                missing.append('Resolve evidence marked as both supporting and contradicting.')
                overlap = set(support) & set(contradict)
                rejected.extend(sorted(overlap))
                support = [i for i in support if i not in overlap]
                contradict = [i for i in contradict if i not in overlap]
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=item.get("hypothesis_id") or f"H-{index:03d}",
                    title=item.get("title") or f"Hypothesis {index}",
                    description=item.get("description") or "",
                    supporting_evidence_ids=support,
                    contradicting_evidence_ids=contradict,
                    missing_evidence=missing,
                    verification_steps=list(item.get("verification_steps", []) or []),
                    assessment=assessment,
                )
            )
        return hypotheses, rejected

    @staticmethod
    def _recommended_actions(hypotheses: list[Hypothesis]) -> list[RecommendedAction]:
        actions: list[RecommendedAction] = []
        seen: set[str] = set()
        for hypothesis in hypotheses:
            for step in hypothesis.verification_steps:
                if step and step not in seen:
                    seen.add(step)
                    actions.append(
                        RecommendedAction(
                            action=step,
                            rationale=f"Verification step for '{hypothesis.title}'.",
                            requires_human_approval=True,
                            supporting_hypothesis_ids=[hypothesis.hypothesis_id],
                        )
                    )
        actions.append(
            RecommendedAction(
                action=(
                    "Have a qualified technician confirm the findings using approved "
                    "procedures before any physical intervention."
                ),
                rationale="AI-assisted findings always require human verification.",
                requires_human_approval=True,
                supporting_hypothesis_ids=[],
            )
        )
        return actions[:MAX_RECOMMENDED_ACTIONS]

    @staticmethod
    def _check_excluded_citations(draft, counterfactual, deterministic_findings):
        excluded_evidence_reused: list[str] = []
        if counterfactual:
            excluded_ids = set(counterfactual.get("excluded_evidence_ids", []) or [])
            raw_cited: set[str] = set()
            for item in draft.get("hypotheses", []) or []:
                raw_cited.update(item.get("supporting_evidence_ids", []) or [])
                raw_cited.update(item.get("contradicting_evidence_ids", []) or [])
            excluded_evidence_reused = sorted(excluded_ids & raw_cited)
            if excluded_evidence_reused:
                deterministic_findings.append(
                    "Excluded evidence was reused in the draft and removed: "
                    + ", ".join(excluded_evidence_reused)
                )
            else:
                deterministic_findings.append(
                    "Deterministic check: no excluded evidence was reused in the "
                    "revised reasoning."
                )
        return excluded_evidence_reused

    def _build_report(
        self,
        investigation_id: str,
        incident_id: str,
        draft: dict[str, Any],
        hypotheses: list[Hypothesis],
        critic_output: dict[str, Any],
        rejected: list[str],
        evidence_records: list[dict[str, Any]],
        revision_count: int,
        counterfactual: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        rejected_unique = sorted(set(rejected))
        deterministic_findings: list[str] = list(critic_output.get('deterministic_findings', []))
        if rejected_unique:
            deterministic_findings.append(
                "Rejected invalid or conflicting evidence references: "
                + ", ".join(rejected_unique)
            )

        excluded_evidence_reused = self._check_excluded_citations(
            draft, counterfactual, deterministic_findings
        )

        critic_review = CriticReview(
            verification_outcome=critic_output.get("verification_outcome")
            or "reviewed",
            issues_found=list(critic_output.get("issues_found", []) or []),
            unsupported_claims=list(critic_output.get("unsupported_claims", []) or []),
            contradictions=list(critic_output.get("contradictions", []) or []),
            alternative_explanations=list(
                critic_output.get("alternative_explanations", []) or []
            ),
            missing_evidence=list(critic_output.get("missing_evidence", []) or []),
            citation_issues=list(critic_output.get("citation_issues", []) or []),
            citation_reviews=list(critic_output.get('citation_reviews', []) or []),
            revision_required=bool(critic_output.get("revision_required"))
            or bool(rejected_unique),
            deterministic_findings=deterministic_findings,
            excluded_evidence_reused=excluded_evidence_reused,
        )

        return {
            "investigation_id": investigation_id,
            "incident_id": incident_id,
            "status": "completed",
            "summary": draft.get("summary") or "Investigation completed.",
            "provider": self.runtime.provider,
            "model": self.runtime.model_name,
            "generated_at": _utcnow_iso(),
            "hypotheses": [hypothesis.model_dump() for hypothesis in hypotheses],
            "critic_review": critic_review.model_dump(),
            "recommended_actions": [
                action.model_dump() for action in self._recommended_actions(hypotheses)
            ],
            "agent_activity": [],
            "evidence_catalog": [record["evidence_id"] for record in evidence_records],
            "rejected_citations": rejected_unique,
            "revision_count": revision_count,
            "counterfactual": counterfactual,
            "disclaimer": REPORT_DISCLAIMER,
        }


__all__ = [
    "Orchestrator",
    "InvestigationResult",
    "PreparedContext",
    "InvestigationError",
    "InvestigationDisabledError",
    "ProgressReporter",
]
