"""Fail-closed checks for source identifiers and explicit measured quantities.

These checks verify provenance and numbers; semantic support still requires
the independent critic and human verification.
"""
from __future__ import annotations

import math
import re
from typing import Any

from services.api.tools.evidence_tools import validate_evidence_ids

_SOURCE_ID = re.compile(r"\b(?:DOC|SEC|EV)-[A-Za-z0-9-]+")
_QUANTITY = re.compile(
    r"(?<![\w.-])(-?\d+(?:\.\d+)?)\s*(rpm|Nm|N\s*[·⋅]\s*m|kW|W|°C|K|min)\b",
    re.IGNORECASE,
)


def text_issues(text: str, records: list[dict[str, Any]]) -> list[str]:
    identifiers = {r['evidence_id'] for r in records}
    for record in records:
        payload = record.get('payload') or {}
        identifiers.update(str(payload[k]) for k in ('document_id', 'section_id') if payload.get(k))
    issues = [f"Unknown source reference: {identifier}" for identifier in _SOURCE_ID.findall(text)
              if identifier not in identifiers]
    for match in _QUANTITY.finditer(text):
        value, unit = float(match[1]), match[2].lower().replace(' ', '')
        if unit in ('n·m', 'n⋅m'):
            unit = 'nm'
        if unit == 'kw':
            unit, value = 'w', value * 1000
        allowed = [float(r['value']) for r in records
                   if r.get('value') is not None and str(r.get('units', '')).lower() == unit]
        if unit == 'k':
            allowed.extend(float(r['value']) + 273.15 for r in records
                           if r.get('value') is not None and r.get('units') == '°C'
                           and r.get('payload', {}).get('feature') != 'temperature_difference_c')
        # Accept display rounding, but never a model-derived new measurement.
        precision = len(match[1].split('.')[1]) if '.' in match[1] else 0
        tolerance = 0.5 * 10 ** -precision * (1000 if match[2].lower() == 'kw' else 1) + 1e-6
        if not any(math.isclose(value, x, rel_tol=0, abs_tol=tolerance) for x in allowed):
            issues.append(f"Unverified numerical measurement: {match[0]}")
    for match in re.finditer(r"(?:robust\s+)?z[- ]?score\s*(?:of|is|=|:)?\s*(-?\d+(?:\.\d+)?)", text, re.IGNORECASE):
        value = float(match[1])
        allowed = [r.get('payload', {}).get('robust_zscore') for r in records]
        if not any(x is not None and math.isclose(value, float(x), abs_tol=0.005) for x in allowed):
            issues.append(f'Unverified statistic: {match[0]}')
    return list(dict.fromkeys(issues))


def validate_sensor_snapshot(measurements: dict, anomaly: dict) -> None:
    """Ensure the recorded physical observations match the scored observations."""
    raw = measurements.get('measurements', {})
    derived = raw.get('derived_features', {})
    rpm, torque = raw.get('rotational_speed_rpm'), raw.get('torque_nm')
    for name, value in (('rotational_speed_rpm', rpm), ('torque_nm', torque)):
        if value is None or not math.isfinite(float(value)):
            raise ValueError(f'Missing or non-finite sensor measurement: {name}')
        if not math.isclose(float(value), float(derived.get(name, float('nan'))), abs_tol=0.0001):
            raise ValueError(f'Raw and derived sensor measurements differ: {name}')
    power = float(torque) * 2 * math.pi * float(rpm) / 60
    if not math.isfinite(power) or not math.isclose(float(derived.get('mechanical_power_w', float('nan'))), power, abs_tol=0.0001):
        raise ValueError('Mechanical power is inconsistent with recorded torque and rotational speed')
    for feature in anomaly.get('features', []):
        key = feature['feature']
        observed = derived.get(key)
        if observed is None or not math.isfinite(float(observed)):
            raise ValueError(f'Missing or non-finite sensor measurement: {key}')
        if not math.isclose(float(observed), float(feature['observed_value']), abs_tol=0.0001):
            raise ValueError(f'Incident snapshot differs from detector observation: {key}')


def normalize_analysis(output: dict, catalog: dict, kind: str) -> tuple[dict, list[str]]:
    """Use item-level valid citations, never trust the redundant count field."""
    allowed_types = ({'manual_passage'} if kind == 'knowledge' else
                     {'sensor_measurement', 'baseline_statistic', 'anomaly_finding', 'source_metadata'})
    allowed = {k: v for k, v in catalog.items() if v['evidence_type'] in allowed_types}
    key = 'guidance' if kind == 'knowledge' else 'findings'
    text_key = 'guidance' if kind == 'knowledge' else 'observation'
    issues: list[str] = []
    items = []
    cited: list[str] = []
    for item in output.get(key, []):
        ids, rejected = validate_evidence_ids(item.get('evidence_ids', []), allowed)
        problems = text_issues(item.get(text_key, ''), [allowed[i] for i in ids])
        if rejected or problems or not ids:
            issues.extend([f"{kind}: rejected evidence ID {i}" for i in rejected])
            issues.extend(problems or [f"{kind}: uncited {key} removed"])
            continue
        items.append({**item, 'evidence_ids': ids})
        cited.extend(ids)
    _, rejected = validate_evidence_ids(output.get('referenced_evidence_ids', []), allowed)
    issues.extend(f"{kind}: rejected evidence ID {i}" for i in rejected)
    summary = output.get('summary', '')
    summary_issues = text_issues(summary, list(allowed.values()))
    issues.extend(summary_issues)
    if summary_issues or not items:
        summary = ("No validated maintenance guidance is available; documentation is missing."
                   if kind == 'knowledge' else "No validated sensor interpretation was returned. Review deterministic evidence.")
    return {**output, key: items, 'summary': summary,
            'referenced_evidence_ids': list(dict.fromkeys(cited))}, issues


def critic_requires_revision(output: dict) -> bool:
    return bool(output.get('revision_required') or any(output.get(k) for k in
                ('issues_found', 'unsupported_claims', 'contradictions', 'citation_issues')))
