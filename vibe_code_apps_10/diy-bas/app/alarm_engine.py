from __future__ import annotations

import time
from typing import Any, Callable

from . import alarm_runtime_store, json_store, trend_store


def _fmt_val(val: Any) -> str:
    if val is None:
        return ''
    if isinstance(val, bool):
        return 'true' if val else 'false'
    return str(val)


def _coerce_float(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, bool):
        return 1.0 if val else 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _normalize_bool(val: Any) -> bool | None:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        if val == 0:
            return False
        if val == 1:
            return True
        return None
    if isinstance(val, str):
        s = val.strip().lower()
        if s in ('true', 'on', 'active', 'yes', '1'):
            return True
        if s in ('false', 'off', 'inactive', 'no', '0'):
            return False
    return None


def _values_equivalent(va: Any, vb: Any) -> bool:
    na, nb = _coerce_float(va), _coerce_float(vb)
    if na is not None and nb is not None:
        return abs(na - nb) < 1e-9
    ba, bb = _normalize_bool(va), _normalize_bool(vb)
    if ba is not None and bb is not None:
        return ba == bb
    return _fmt_val(va) == _fmt_val(vb)


def _live_values_map() -> dict[str, Any]:
    doc = json_store.read_json('latest_values.json', {'updatedAt': None, 'values': {}})
    vals = doc.get('values')
    return vals if isinstance(vals, dict) else {}


def _row_val(vals: dict[str, Any], pid: str) -> tuple[Any | None, bool]:
    """Return (raw_value, ok) where ok is False if missing or BACnet error."""
    row = vals.get(pid) if isinstance(vals.get(pid), dict) else None
    if not isinstance(row, dict):
        return None, False
    if row.get('lastError'):
        return row.get('value'), False
    return row.get('value'), True


def _delay_gate(
    rule_key: str,
    delay_sec: int,
    now: int,
    violation: bool,
    on_allowed_fire: Callable[[], None],
    on_clear: Callable[[], None],
) -> None:
    d = max(0, int(delay_sec or 0))
    if not violation:
        trend_store.alarm_delay_clear(rule_key)
        on_clear()
        return
    if d <= 0:
        on_allowed_fire()
        return
    since = trend_store.alarm_delay_get(rule_key)
    if since is None:
        trend_store.alarm_delay_set(rule_key, now)
        return
    if now - int(since) >= d:
        on_allowed_fire()


def _eval_device_offline(pts: list[dict[str, Any]], now: int) -> None:
    watch: set[int] = set()
    for p in pts:
        if not p.get('pollingEnabled'):
            continue
        di = int(p.get('deviceInstance') or 0)
        if di:
            watch.add(di)
    if not watch:
        for r in trend_store.list_open_alarm_events():
            if str(r.get('kind') or '') != 'device_offline':
                continue
            pkey = str(r.get('pointId') or '')
            if pkey.startswith('device:'):
                trend_store.close_open_alarm_event(pkey, 'device_offline', now, 'no polled devices')
        return

    doc = alarm_runtime_store.read_runtime()
    offline_sec = alarm_runtime_store.get_device_offline_sec()
    succ_map = doc.get('lastDevicePollSuccessTs')
    batch_map = doc.get('lastDevicePollBatchTs')
    if not isinstance(succ_map, dict):
        succ_map = {}
    if not isinstance(batch_map, dict):
        batch_map = {}

    for di in sorted(watch):
        sk = str(int(di))
        succ_v = succ_map.get(sk)
        batch_v = batch_map.get(sk)
        succ_ts = int(succ_v) if succ_v is not None else None
        batch_ts = int(batch_v) if batch_v is not None else None
        stale = False
        if succ_ts is not None:
            stale = now - succ_ts >= offline_sec
        elif batch_ts is not None:
            stale = now - batch_ts >= offline_sec
        pid = f'device:{di}'
        if stale:
            trend_store.try_insert_open_alarm_event(
                pid,
                'device_offline',
                f'BACnet device {di} has not responded successfully for {offline_sec}s',
                now,
                '',
            )
        else:
            trend_store.close_open_alarm_event(pid, 'device_offline', now, 'online')


def evaluate_alarms_for_live_values(point_ids: set[str] | None) -> None:
    """Update open/closed alarm_events from latest_values + alarm_rules (+ device offline)."""
    rules = trend_store.read_alarm_rules()
    vals = _live_values_map()
    now = int(time.time())
    pts = trend_store.read_points_merged_with_polling()

    for rule in rules:
        pid = str(rule.get('pointId') or '').strip()
        if not pid:
            continue
        rk = str(rule.get('ruleKind') or 'threshold').strip() or 'threshold'
        if point_ids is not None and pid not in point_ids:
            if rk != 'cross_compare':
                continue
            bid = str(rule.get('comparePointId') or '').strip()
            if bid not in point_ids:
                continue

        if not bool(rule.get('enabled', True)):
            for kind in ('threshold_low', 'threshold_high', 'bool_mismatch', 'cross_mismatch'):
                trend_store.close_open_alarm_event(pid, kind, now, '(rule disabled)')
            continue

        if rk == 'cross_compare':
            _eval_cross_rule(rule, pid, vals, now)
            continue

        row_ok = _row_val(vals, pid)
        raw_val, ok = row_ok
        if not ok:
            continue

        ptype = str(rule.get('pointType') or 'numeric').lower()
        if ptype == 'bool':
            _eval_bool_rule(rule, pid, raw_val, now)
        else:
            _eval_numeric_rule(rule, pid, raw_val, now)

    _eval_device_offline(pts, now)


def _eval_cross_rule(rule: dict[str, Any], pid: str, vals: dict[str, Any], now: int) -> None:
    bid = str(rule.get('comparePointId') or '').strip()
    if not bid or bid == pid:
        return
    op = str(rule.get('compareOperator') or 'eq').strip() or 'eq'
    if op not in ('eq', 'ne'):
        op = 'eq'
    va, oka = _row_val(vals, pid)
    vb, okb = _row_val(vals, bid)
    if not oka or not okb:
        return
    try:
        raw = int(
            float(
                rule.get('delaySec')
                if rule.get('delaySec') is not None
                else (rule.get('boolDelaySec') if rule.get('boolDelaySec') is not None else 0)
            )
        )
    except (TypeError, ValueError):
        raw = 0
    delay = max(10, min(raw if raw > 0 else 300, 86400))
    eq = _values_equivalent(va, vb)
    mismatch = (not eq) if op == 'eq' else eq
    vstr = f'A={_fmt_val(va)} B={_fmt_val(vb)}'
    key = f'{pid}:cross_mismatch'

    def fire() -> None:
        msg = f'Status vs command mismatch (expected equal; {delay}s hold): vs {bid}'
        trend_store.try_insert_open_alarm_event(pid, 'cross_mismatch', msg, now, vstr)

    def clear() -> None:
        trend_store.close_open_alarm_event(pid, 'cross_mismatch', now, vstr)

    _delay_gate(key, delay, now, mismatch, fire, clear)


def _eval_bool_rule(rule: dict[str, Any], pid: str, raw_val: Any, now: int) -> None:
    expected = rule.get('expectedBool')
    if expected is None:
        return
    exp = bool(expected)
    nv = _normalize_bool(raw_val)
    if nv is None:
        return
    kind = 'bool_mismatch'
    vstr = _fmt_val(raw_val)
    delay = int(rule.get('delaySec') if rule.get('delaySec') is not None else rule.get('boolDelaySec') or 0)
    violation = nv != exp
    key = f'{pid}:{kind}'

    def fire() -> None:
        trend_store.try_insert_open_alarm_event(
            pid, kind, f'Present value {vstr} ≠ expected normal {_fmt_val(exp)}', now, vstr
        )

    def clear() -> None:
        trend_store.close_open_alarm_event(pid, kind, now, vstr)

    _delay_gate(key, delay, now, violation, fire, clear)


def _eval_numeric_rule(rule: dict[str, Any], pid: str, raw_val: Any, now: int) -> None:
    low = rule.get('lowThreshold')
    high = rule.get('highThreshold')
    delay = int(rule.get('delaySec') if rule.get('delaySec') is not None else rule.get('boolDelaySec') or 0)
    dead = float(rule.get('deadband') or 0.0)
    n = _coerce_float(raw_val)
    if n is None:
        return
    vstr = _fmt_val(raw_val)

    if low is None and high is None:
        for kind in ('threshold_low', 'threshold_high'):
            trend_store.close_open_alarm_event(pid, kind, now, vstr)
            trend_store.alarm_delay_clear(f'{pid}:{kind}')
        return

    if low is not None:
        lo = float(low)
        kind = 'threshold_low'
        key = f'{pid}:{kind}'

        def fire_lo() -> None:
            trend_store.try_insert_open_alarm_event(pid, kind, f'Below low limit ({lo})', now, vstr)

        if n < lo:
            _delay_gate(key, delay, now, True, fire_lo, lambda: None)
        elif n >= lo + dead:
            trend_store.alarm_delay_clear(key)
            trend_store.close_open_alarm_event(pid, kind, now, vstr)
        else:
            trend_store.alarm_delay_clear(key)

    if high is not None:
        hi = float(high)
        kind = 'threshold_high'
        key = f'{pid}:{kind}'

        def fire_hi() -> None:
            trend_store.try_insert_open_alarm_event(pid, kind, f'Above high limit ({hi})', now, vstr)

        if n > hi:
            _delay_gate(key, delay, now, True, fire_hi, lambda: None)
        elif n <= hi - dead:
            trend_store.alarm_delay_clear(key)
            trend_store.close_open_alarm_event(pid, kind, now, vstr)
        else:
            trend_store.alarm_delay_clear(key)


def attach_alarm_flags_to_points(points: list[dict[str, Any]]) -> None:
    active = trend_store.list_open_alarm_events()
    by_pid: dict[str, dict[str, Any]] = {}
    device_offline_dis: set[int] = set()
    for r in active:
        pkey = str(r.get('pointId') or '')
        if not pkey:
            continue
        if pkey.startswith('device:') and str(r.get('kind') or '') == 'device_offline':
            try:
                device_offline_dis.add(int(pkey.split(':', 1)[1]))
            except ValueError:
                continue
            continue
        agg = by_pid.setdefault(pkey, {'kinds': [], 'messages': [], 'details': []})
        agg['kinds'].append(str(r.get('kind') or ''))
        agg['messages'].append(str(r.get('message') or ''))
        agg['details'].append(
            {
                'kind': str(r.get('kind') or ''),
                'message': str(r.get('message') or ''),
                'openedAt': str(r.get('openedAt') or ''),
                'valueAtOpen': str(r.get('valueOpen') or ''),
            }
        )

    for p in points:
        pid = str(p.get('pointId') or '')
        di = int(p.get('deviceInstance') or 0)
        dev_off = di in device_offline_dis
        p['deviceOfflineAlarm'] = dev_off
        agg = by_pid.get(pid)
        if agg or dev_off:
            p['inAlarm'] = True
            kinds = list(agg['kinds']) if agg else []
            msgs = list(agg['messages']) if agg else []
            details = list(agg['details']) if agg else []
            if dev_off:
                kinds.append('device_offline')
                msgs.append(f'Device {di} offline (BACnet)')
                details.append(
                    {
                        'kind': 'device_offline',
                        'message': f'Device {di} offline (BACnet)',
                        'openedAt': '',
                        'valueAtOpen': '',
                    }
                )
            p['alarmKinds'] = kinds
            p['alarmSummary'] = '; '.join(msgs[:4])
            p['alarmDetails'] = details
        else:
            p['inAlarm'] = False
            p['alarmKinds'] = []
            p['alarmSummary'] = ''
            p['alarmDetails'] = []


def attach_device_alarm_flags(devices: list[dict[str, Any]]) -> None:
    active = trend_store.list_open_alarm_events()
    off: set[int] = set()
    for r in active:
        if str(r.get('kind') or '') != 'device_offline':
            continue
        pkey = str(r.get('pointId') or '')
        if not pkey.startswith('device:'):
            continue
        try:
            off.add(int(pkey.split(':', 1)[1]))
        except ValueError:
            continue
    for d in devices:
        di = int(d.get('deviceInstance') or 0)
        d['deviceOfflineAlarm'] = di in off
