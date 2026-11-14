# ai-generated: 100% - Claude Code (Opus 5.5) wrote these tests from the docstrings of slaclock.py, aiming at every boundary
"""Behaviour tests for slaclock.py (Lab 5, Stretch 1, P-29): the docstrings are the specification.

Every test calls the module inside the test function, so a mutant that raises fails a test instead of breaking
collection, and no test reads the module's text, so a behaviour-preserving rewrite passes.
"""

from datetime import datetime, timedelta

import pytest

import slaclock

MON = datetime(2026, 1, 5)  # a Monday, midnight
TUE, WED, THU, FRI, SAT, SUN = (MON + timedelta(days=n) for n in range(1, 7))
NEXT_MON = MON + timedelta(days=7)


def at(day, hour, minute=0, second=0):
    return day.replace(hour=hour, minute=minute, second=second)


# ------------------------------------------------------------------ priority_of

@pytest.mark.parametrize("impact, urgency, expected", [
    (1, 1, "P1"),
    (1, 2, "P2"), (2, 1, "P2"),
    (1, 3, "P3"), (2, 2, "P3"), (3, 1, "P3"),
    (2, 3, "P4"), (3, 2, "P4"), (3, 3, "P4"),
])
def test_priority_matrix(impact, urgency, expected):
    assert slaclock.priority_of(impact, urgency) == expected
    assert slaclock.priority_of(impact, urgency, vip=False) == expected


@pytest.mark.parametrize("impact, urgency, expected", [
    (1, 1, "P1"),
    (1, 2, "P2"), (2, 1, "P2"),
    (1, 3, "P2"), (2, 2, "P2"), (3, 1, "P2"),
    (2, 3, "P2"), (3, 2, "P2"), (3, 3, "P2"),
])
def test_priority_vip_never_below_p2(impact, urgency, expected):
    assert slaclock.priority_of(impact, urgency, vip=True) == expected
    assert slaclock.priority_of(impact, urgency, True) == expected


@pytest.mark.parametrize("bad", [0, 4, -1, 2.0, 1.0, True, False, "1", None])
def test_priority_rejects_bad_impact_and_urgency(bad):
    with pytest.raises(ValueError):
        slaclock.priority_of(bad, 1)
    with pytest.raises(ValueError):
        slaclock.priority_of(1, bad)
    with pytest.raises(ValueError):
        slaclock.priority_of(bad, 3, vip=True)
    with pytest.raises(ValueError):
        slaclock.priority_of(3, bad, vip=True)


# ------------------------------------------------------------------ targets

@pytest.mark.parametrize("priority, expected", [
    ("P1", (15, 240)), ("P2", (60, 480)), ("P3", (240, 1440)), ("P4", (480, 4320)),
])
def test_targets(priority, expected):
    assert slaclock.targets(priority) == expected
    response, resolution = slaclock.targets(priority)
    assert (response, resolution) == expected


@pytest.mark.parametrize("bad", ["p1", " P1", "P1 ", "P5", "P0", "", "P"])
def test_targets_lookup_is_exact(bad):
    with pytest.raises(ValueError):
        slaclock.targets(bad)


# ------------------------------------------------------------------ sla_state

@pytest.mark.parametrize("elapsed, target, expected", [
    (0, 15, "ok"), (11, 15, "ok"), (12, 15, "warning"), (15, 15, "warning"), (16, 15, "breached"),
    (0, 100, "ok"), (74, 100, "ok"), (75, 100, "warning"), (99, 100, "warning"), (100, 100, "warning"),
    (101, 100, "breached"), (500, 100, "breached"),
    (0, 4, "ok"), (2, 4, "ok"), (3, 4, "warning"), (4, 4, "warning"), (5, 4, "breached"),
    (0, 1, "ok"), (1, 1, "warning"), (2, 1, "breached"),
    (179, 240, "ok"), (180, 240, "warning"), (240, 240, "warning"), (241, 240, "breached"),
])
def test_sla_state(elapsed, target, expected):
    assert slaclock.sla_state(elapsed, target) == expected


@pytest.mark.parametrize("elapsed, target", [(-1, 15), (0, 0), (5, 0), (0, -1), (-5, -5)])
def test_sla_state_rejects(elapsed, target):
    with pytest.raises(ValueError):
        slaclock.sla_state(elapsed, target)


# ------------------------------------------------------------------ is_business_time

@pytest.mark.parametrize("moment, expected", [
    (at(MON, 7, 59), False), (at(MON, 8, 0), True), (at(MON, 12, 0), True), (at(MON, 15, 59), True),
    (at(MON, 16, 0), False), (at(MON, 16, 1), False), (at(MON, 0, 0), False), (at(MON, 23, 59), False),
    (at(MON, 7, 59, 59), False), (at(MON, 15, 59, 59), True),
    (at(TUE, 8, 0), True), (at(WED, 10, 0), True), (at(THU, 14, 0), True),
    (at(FRI, 8, 0), True), (at(FRI, 15, 59), True), (at(FRI, 16, 0), False),
    (at(SAT, 8, 0), False), (at(SAT, 12, 0), False), (at(SUN, 8, 0), False), (at(SUN, 15, 59), False),
])
def test_is_business_time(moment, expected):
    assert slaclock.is_business_time(moment) is expected


# ------------------------------------------------------------------ add_business_minutes

@pytest.mark.parametrize("start, minutes, expected", [
    (at(MON, 8, 0), 0, at(MON, 8, 0)),
    (at(MON, 9, 30), 0, at(MON, 9, 30)),
    (at(MON, 15, 59), 0, at(MON, 15, 59)),
    (at(MON, 7, 0), 0, at(MON, 8, 0)),
    (at(MON, 0, 0), 0, at(MON, 8, 0)),
    (at(MON, 16, 0), 0, at(TUE, 8, 0)),
    (at(FRI, 16, 0), 0, at(NEXT_MON, 8, 0)),
    (at(SAT, 10, 0), 0, at(NEXT_MON, 8, 0)),
    (at(SUN, 23, 59), 0, at(NEXT_MON, 8, 0)),
    (at(MON, 8, 0), 1, at(MON, 8, 1)),
    (at(MON, 8, 0), 15, at(MON, 8, 15)),
    (at(MON, 8, 0), 479, at(MON, 15, 59)),
    (at(MON, 8, 0), 480, at(MON, 16, 0)),
    (at(MON, 8, 0), 481, at(TUE, 8, 1)),
    (at(MON, 8, 0), 960, at(TUE, 16, 0)),
    (at(MON, 8, 0), 961, at(WED, 8, 1)),
    (at(MON, 7, 0), 30, at(MON, 8, 30)),
    (at(MON, 15, 0), 60, at(MON, 16, 0)),
    (at(MON, 15, 0), 61, at(TUE, 8, 1)),
    (at(MON, 15, 30), 240, at(TUE, 11, 30)),
    (at(MON, 17, 0), 60, at(TUE, 9, 0)),
    (at(FRI, 15, 0), 60, at(FRI, 16, 0)),
    (at(FRI, 15, 0), 61, at(NEXT_MON, 8, 1)),
    (at(FRI, 14, 0), 240, at(NEXT_MON, 10, 0)),
    (at(SAT, 9, 0), 1, at(NEXT_MON, 8, 1)),
    (at(SUN, 9, 0), 480, at(NEXT_MON, 16, 0)),
    (at(MON, 8, 0), 5 * 480, at(FRI, 16, 0)),
    (at(MON, 8, 0), 5 * 480 + 1, at(NEXT_MON, 8, 1)),
    (at(MON, 8, 0, 59), 1, at(MON, 8, 1)),
    (at(MON, 15, 59, 30), 1, at(MON, 16, 0)),
    (at(MON, 7, 59, 59), 0, at(MON, 8, 0)),
])
def test_add_business_minutes(start, minutes, expected):
    assert slaclock.add_business_minutes(start, minutes) == expected


def test_add_business_minutes_result_has_no_seconds():
    due = slaclock.add_business_minutes(at(MON, 9, 0, 45), 10)
    assert due == at(MON, 9, 10)
    assert due.second == 0 and due.microsecond == 0


@pytest.mark.parametrize("minutes", [-1, -480])
def test_add_business_minutes_rejects_negative(minutes):
    with pytest.raises(ValueError):
        slaclock.add_business_minutes(at(MON, 8, 0), minutes)


def test_add_business_minutes_limit_of_max_days():
    # From Monday 2026-01-05 the calendar days 0..366 end on Wednesday 2027-01-06 and hold 263 business days.
    last = MON + timedelta(days=366)
    assert slaclock.add_business_minutes(at(MON, 8, 0), 263 * 480) == at(last, 16, 0)
    assert slaclock.add_business_minutes(at(MON, 8, 0), 263 * 480 - 1) == at(last, 15, 59)
    with pytest.raises(ValueError):
        slaclock.add_business_minutes(at(MON, 8, 0), 263 * 480 + 1)
    with pytest.raises(ValueError):
        slaclock.add_business_minutes(at(MON, 8, 0), 10 ** 6)


# ------------------------------------------------------------------ business_minutes_between

@pytest.mark.parametrize("start, end, expected", [
    (at(MON, 8, 0), at(MON, 8, 0), 0),
    (at(MON, 10, 0), at(MON, 10, 0), 0),
    (at(SAT, 10, 0), at(SAT, 10, 0), 0),
    (at(MON, 8, 0), at(MON, 8, 1), 1),
    (at(MON, 8, 0), at(MON, 16, 0), 480),
    (at(MON, 0, 0), at(TUE, 0, 0), 480),
    (at(MON, 7, 0), at(MON, 9, 0), 60),
    (at(MON, 15, 0), at(MON, 17, 0), 60),
    (at(MON, 15, 59), at(MON, 16, 0), 1),
    (at(MON, 16, 0), at(MON, 16, 1), 0),
    (at(MON, 7, 59), at(MON, 8, 0), 0),
    (at(MON, 7, 0), at(MON, 7, 59), 0),
    (at(MON, 17, 0), at(MON, 23, 0), 0),
    (at(MON, 15, 0), at(TUE, 9, 0), 120),
    (at(MON, 8, 0), at(TUE, 16, 0), 960),
    (at(MON, 8, 0), at(NEXT_MON, 8, 0), 2400),
    (at(FRI, 15, 0), at(NEXT_MON, 9, 0), 120),
    (at(FRI, 16, 0), at(NEXT_MON, 8, 0), 0),
    (at(SAT, 0, 0), at(SUN, 23, 59), 0),
    (at(SAT, 12, 0), at(NEXT_MON, 8, 30), 30),
    (at(MON, 8, 0, 30), at(MON, 8, 1, 10), 1),
    (at(MON, 8, 0, 59), at(MON, 8, 0, 1), 0),
    (at(WED, 12, 0), at(THU, 12, 0), 480),
])
def test_business_minutes_between(start, end, expected):
    assert slaclock.business_minutes_between(start, end) == expected


def test_business_minutes_between_rejects_end_before_start():
    with pytest.raises(ValueError):
        slaclock.business_minutes_between(at(MON, 9, 0), at(MON, 8, 59))
    with pytest.raises(ValueError):
        slaclock.business_minutes_between(at(TUE, 9, 0), at(MON, 9, 0))


def test_business_minutes_between_limit_of_max_days():
    last = MON + timedelta(days=366)
    assert slaclock.business_minutes_between(at(MON, 8, 0), at(last, 16, 0)) == 263 * 480
    assert slaclock.business_minutes_between(at(MON, 0, 0), at(last, 23, 59)) == 263 * 480
    with pytest.raises(ValueError):
        slaclock.business_minutes_between(at(MON, 8, 0), at(MON + timedelta(days=367), 0, 0))


@pytest.mark.parametrize("start", [
    at(MON, 8, 0), at(MON, 7, 0), at(MON, 15, 59), at(MON, 16, 0), at(FRI, 15, 30), at(SAT, 10, 0),
    at(SUN, 23, 59), at(WED, 11, 17),
])
@pytest.mark.parametrize("minutes", [0, 1, 59, 60, 479, 480, 481, 1000, 2400, 2401, 5000])
def test_round_trip(start, minutes):
    due = slaclock.add_business_minutes(start, minutes)
    assert slaclock.business_minutes_between(start, due) == minutes


# ------------------------------------------------------------------ escalation_tier

@pytest.mark.parametrize("priority, breached, reopens, expected", [
    ("P1", False, 0, 1), ("P1", False, 1, 1), ("P1", False, 2, 2), ("P1", False, 5, 2),
    ("P1", True, 0, 3), ("P1", True, 1, 3), ("P1", True, 2, 3),
    ("P2", False, 0, 1), ("P2", False, 1, 1), ("P2", False, 2, 2),
    ("P2", True, 0, 2), ("P2", True, 1, 2), ("P2", True, 2, 3), ("P2", True, 9, 3),
    ("P3", False, 0, 0), ("P3", False, 1, 0), ("P3", False, 2, 1),
    ("P3", True, 0, 1), ("P3", True, 1, 1), ("P3", True, 2, 2),
    ("P4", False, 0, 0), ("P4", False, 1, 0), ("P4", False, 2, 1), ("P4", False, 3, 1),
    ("P4", True, 0, 1), ("P4", True, 2, 2),
])
def test_escalation_tier(priority, breached, reopens, expected):
    assert slaclock.escalation_tier(priority, breached, reopens) == expected


@pytest.mark.parametrize("priority, reopens", [("P5", 0), ("p1", 0), (" P1", 0), ("", 0), ("P1", -1), ("P4", -3)])
def test_escalation_tier_rejects(priority, reopens):
    with pytest.raises(ValueError):
        slaclock.escalation_tier(priority, False, reopens)
    with pytest.raises(ValueError):
        slaclock.escalation_tier(priority, True, reopens)


# ------------------------------------------------------------------ parse_duration

@pytest.mark.parametrize("text, expected", [
    ("90m", 90), ("4h", 240), ("1h30m", 90), ("2d", 2880), ("1d4h", 1680), ("1d0h5m", 1445),
    ("1h59m", 119), ("60m", 60), ("0h60m", 60), ("0d60m", 60), ("0d0h60m", 60), ("1m", 1), ("59m", 59),
    ("1d", 1440), ("1h", 60), ("25h", 1500), ("1d1h1m", 1501), ("3d2h", 4440), ("2d30m", 2910),
    ("1d59m", 1499), ("120m", 120), ("0d1h", 60), ("0h1m", 1), ("10d", 14400),
    ("  90m  ", 90), ("\t1h\n", 60), (" 1d4h ", 1680),
])
def test_parse_duration(text, expected):
    assert slaclock.parse_duration(text) == expected


@pytest.mark.parametrize("bad", [
    "", "   ", "0m", "0h", "0d", "0d0h0m", "1.5h", "30m1h", "4h1d", "-5m", "1 h", "1h 30m", "1h60m", "1d60m",
    "1d0h60m", "2h75m", "5M", "1H", "1D", "m", "h", "d", "5", "1h30", "1x", "1m1m", "1h1h", "abc", "+5m",
])
def test_parse_duration_rejects(bad):
    with pytest.raises(ValueError):
        slaclock.parse_duration(bad)
