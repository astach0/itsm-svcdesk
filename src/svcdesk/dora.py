# ai-generated: 100% - generated from METRIC-SPEC.md and the published Lab 2 fixture; implementation reviewed against the published rules
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

SPEC_VERSION = '1.0.0'


def parse_instant(value: Any, field: str = 'timestamp') -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f'{field} must be an RFC 3339 instant')
    raw = value[:-1] + '+00:00' if value.endswith('Z') else value
    try:
        dt = datetime.fromisoformat(raw)
    except Exception as exc:
        raise ValueError(f'{field} must be an RFC 3339 instant') from exc
    if dt.tzinfo is None:
        raise ValueError(f'{field} must include a timezone offset')
    return dt.astimezone(timezone.utc)


def rounded_seconds(value: Decimal) -> int:
    return int(value.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def ratio6(num: int, den: int) -> float | None:
    if den == 0:
        return None
    value = (Decimal(num) / Decimal(den)).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
    return float(value)


def median_seconds(values: list[Decimal]) -> int | None:
    if not values:
        return None
    xs = sorted(values)
    n = len(xs)
    if n % 2:
        mid = xs[n // 2]
    else:
        mid = (xs[n // 2 - 1] + xs[n // 2]) / Decimal('2')
    if mid < 0:
        mid = Decimal('0')
    return rounded_seconds(mid)


def _require_string(obj: dict[str, Any], key: str, max_len: int | None = None) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f'{key} must be a non-empty string')
    if max_len is not None and len(value) > max_len:
        raise ValueError(f'{key} is too long')
    return value


def _normalize_events(events: Any) -> list[dict[str, Any]]:
    if not isinstance(events, list):
        raise ValueError('events must be an array')
    first_by_id: dict[str, dict[str, Any]] = {}
    for raw in events:
        if not isinstance(raw, dict):
            raise ValueError('every event must be an object')
        event_id = _require_string(raw, 'event_id', 64)
        if event_id in first_by_id:
            continue
        first_by_id[event_id] = dict(raw)
    return list(first_by_id.values())


def validate_and_parse_events(events: Any) -> list[dict[str, Any]]:
    rows = _normalize_events(events)
    if not rows:
        return []

    shas: dict[str, dict[str, Any]] = {}
    deployments: dict[str, dict[str, Any]] = {}
    incidents: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)

    for row in rows:
        typ = row.get('type')
        if typ not in {'commit', 'deployment', 'incident'}:
            raise ValueError('type must be commit, deployment or incident')
        row['_dt'] = parse_instant(row.get('at'), 'at')

        if typ == 'commit':
            sha = _require_string(row, 'sha', 128)
            if sha in shas:
                raise ValueError(f'duplicate commit sha: {sha}')
            shas[sha] = row
            if not isinstance(row.get('branch'), str):
                raise ValueError('commit branch must be a string')
            change_id = row.get('change_id')
            reverts = row.get('reverts')
            if reverts is None:
                if not isinstance(change_id, str) or not change_id:
                    raise ValueError('commit without reverts must have change_id')
            else:
                if not isinstance(reverts, str) or not reverts:
                    raise ValueError('reverts must name a sha')
                if change_id is not None:
                    raise ValueError('revert commit must have change_id null')

        elif typ == 'deployment':
            deployment_id = _require_string(row, 'deployment_id', 128)
            if deployment_id in deployments:
                raise ValueError(f'duplicate deployment_id: {deployment_id}')
            if not isinstance(row.get('environment'), str) or not row.get('environment'):
                raise ValueError('deployment environment must be a string')
            if row.get('outcome') not in {'success', 'failure'}:
                raise ValueError('deployment outcome must be success or failure')
            commits = row.get('commits')
            if not isinstance(commits, list) or any(not isinstance(x, str) for x in commits):
                raise ValueError('deployment commits must be an array of shas')
            if not isinstance(row.get('unplanned'), bool):
                raise ValueError('deployment unplanned must be boolean')
            caused_by = row.get('caused_by')
            if caused_by is not None and (not isinstance(caused_by, str) or not caused_by):
                raise ValueError('caused_by must be an incident id or null')
            deployments[deployment_id] = row

        else:
            incident_id = _require_string(row, 'incident_id', 128)
            phase = row.get('phase')
            if phase not in {'opened', 'resolved'}:
                raise ValueError('incident phase must be opened or resolved')
            deployments_ref = row.get('deployments')
            if not isinstance(deployments_ref, list) or any(not isinstance(x, str) for x in deployments_ref):
                raise ValueError('incident deployments must be an array')
            if phase in incidents[incident_id]:
                raise ValueError(f'duplicate incident phase: {incident_id}/{phase}')
            incidents[incident_id][phase] = row

    for row in rows:
        typ = row['type']
        if typ == 'commit':
            if row.get('reverts') is not None and row['reverts'] not in shas:
                raise ValueError(f"reverts names missing sha: {row['reverts']}")
        elif typ == 'deployment':
            for sha in row['commits']:
                if sha not in shas:
                    raise ValueError(f'deployment references missing sha: {sha}')
            if row.get('caused_by') is not None and row['caused_by'] not in incidents:
                raise ValueError(f"caused_by names missing incident: {row['caused_by']}")
        else:
            if row['phase'] == 'resolved' and 'opened' not in incidents[row['incident_id']]:
                raise ValueError(f"incident resolved without opened: {row['incident_id']}")
            for dep in row['deployments']:
                if dep not in deployments:
                    raise ValueError(f'incident references missing deployment: {dep}')

    return rows


def _build_change_resolver(commits: dict[str, dict[str, Any]]):
    cache: dict[str, str] = {}
    visiting: set[str] = set()

    def resolve(sha: str) -> str:
        if sha in cache:
            return cache[sha]
        if sha in visiting:
            raise ValueError('revert chain contains a cycle')
        visiting.add(sha)
        row = commits[sha]
        if row.get('reverts') is None:
            result = row['change_id']
        else:
            result = resolve(row['reverts'])
        visiting.remove(sha)
        cache[sha] = result
        return result

    return resolve


def compute_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError('request body must be an object')
    window = payload.get('window')
    if not isinstance(window, dict):
        raise ValueError('window is required')
    if 'from' not in window or 'to' not in window:
        raise ValueError('window.from and window.to are required')
    from_dt = parse_instant(window['from'], 'window.from')
    to_dt = parse_instant(window['to'], 'window.to')
    if to_dt <= from_dt:
        raise ValueError('window.to must be after window.from')

    rows = validate_and_parse_events(payload.get('events'))
    deployments = {r['deployment_id']: r for r in rows if r['type'] == 'deployment'}
    commits = {r['sha']: r for r in rows if r['type'] == 'commit'}

    production = [d for d in deployments.values() if d.get('environment') == 'production' and from_dt <= d['_dt'] < to_dt]
    production.sort(key=lambda d: (d['_dt'], d['deployment_id']))
    successful = [d for d in production if d['outcome'] == 'success']
    failed = [d for d in production if d['outcome'] == 'failure']

    resolve_change = _build_change_resolver(commits)

    # R-08
    first_successful_deployment_for_sha: dict[str, dict[str, Any]] = {}
    for d in successful:
        for sha in d['commits']:
            first_successful_deployment_for_sha.setdefault(sha, d)
    lead_values: list[Decimal] = []
    negative_pairs = 0
    for sha, d in first_successful_deployment_for_sha.items():
        delta = Decimal(str((d['_dt'] - commits[sha]['_dt']).total_seconds()))
        if delta < 0:
            negative_pairs += 1
            delta = Decimal('0')
        lead_values.append(delta)

    # R-12/R-13
    incident_opened: dict[str, datetime] = {}
    incident_resolved: dict[str, datetime] = {}
    incident_deployments: dict[str, set[str]] = {}
    for row in rows:
        if row['type'] != 'incident':
            continue
        iid = row['incident_id']
        incident_deployments.setdefault(iid, set()).update(row['deployments'])
        if row['phase'] == 'opened':
            incident_opened[iid] = row['_dt']
        else:
            incident_resolved[iid] = row['_dt']

    recovered_values: list[Decimal] = []
    open_failures = 0
    for d in failed:
        covers = [iid for iid, dep_ids in incident_deployments.items() if d['deployment_id'] in dep_ids and iid in incident_opened]
        if not covers:
            open_failures += 1
            continue
        iid = min(covers, key=lambda x: (incident_opened[x], x.encode('utf-8')))
        if iid not in incident_resolved:
            open_failures += 1
            continue
        raw = Decimal(str((incident_resolved[iid] - d['_dt']).total_seconds()))
        if raw < 0:
            raw = Decimal('0')
        recovered_values.append(raw)

    intervals: list[tuple[str, datetime, datetime]] = []
    for iid, opened in incident_opened.items():
        intervals.append((iid, opened, incident_resolved.get(iid, to_dt)))
    overlap_pairs = 0
    for i, (_, a_start, a_end) in enumerate(intervals):
        for _, b_start, b_end in intervals[i + 1:]:
            if a_start < b_end and b_start < a_end:
                overlap_pairs += 1

    commits_never_on_main = len({sha for d in production for sha in d['commits'] if commits[sha]['branch'] != 'main'})
    deployments_without_commits = sum(1 for d in production if not d['commits'])

    # R-06/R-07/R-16/R-17
    change_first_commit: dict[str, datetime] = {}
    for sha, row in commits.items():
        change_id = resolve_change(sha)
        if change_id not in change_first_commit or row['_dt'] < change_first_commit[change_id]:
            change_first_commit[change_id] = row['_dt']

    delivered_first_deployment: dict[str, dict[str, Any]] = {}
    for d in successful:
        for sha in d['commits']:
            ch = resolve_change(sha)
            delivered_first_deployment.setdefault(ch, d)

    true_values: list[Decimal] = []
    for ch, d in delivered_first_deployment.items():
        delta = Decimal(str((d['_dt'] - change_first_commit[ch]).total_seconds()))
        if delta < 0:
            delta = Decimal('0')
        true_values.append(delta)

    deployment_count = len(production)
    successful_count = len(successful)
    failed_count = len(failed)
    rework_count = sum(1 for d in production if d['unplanned'] and d.get('caused_by') is not None)
    changes_count = len(change_first_commit)
    revert_chain_count = sum(1 for c in commits.values() if c.get('reverts') is not None)
    window_days = Decimal(str((to_dt - from_dt).total_seconds())) / Decimal('86400')
    frequency = (Decimal(deployment_count) / window_days).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)

    return {
        'spec_version': SPEC_VERSION,
        'window': {'from': window['from'], 'to': window['to']},
        'deployment_frequency_per_day': float(frequency),
        'change_lead_time_seconds_p50': median_seconds(lead_values),
        'failed_deployment_recovery_time_seconds_p50': median_seconds(recovered_values),
        'change_fail_rate': ratio6(failed_count, deployment_count),
        'deployment_rework_rate': ratio6(rework_count, deployment_count),
        'counts': {
            'deployments': deployment_count,
            'successful_deployments': successful_count,
            'failed_deployments': failed_count,
            'recovered_failures': len(recovered_values),
            'open_failures': open_failures,
            'rework_deployments': rework_count,
            'lead_time_pairs': len(lead_values),
            'changes': changes_count,
        },
        'anomalies': {
            'negative_lead_time_pairs': negative_pairs,
            'deployments_without_commits': deployments_without_commits,
            'commits_never_on_main': commits_never_on_main,
            'revert_chains_collapsed': revert_chain_count,
            'overlapping_incident_pairs': overlap_pairs,
        },
        'ground_truth': {
            'changes_delivered': len(delivered_first_deployment),
            'true_change_lead_time_seconds_p50': median_seconds(true_values),
        },
    }

