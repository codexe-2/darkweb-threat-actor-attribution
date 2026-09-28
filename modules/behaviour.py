"""
Module 4 — BEHAVIOURAL ANALYSIS
===============================

Compares temporal activity rhythm: 24-hour posting distribution, weekday
distribution and posting intensity. Circular smoothing is applied to the hour
histogram so that 23:00 and 00:00 count as neighbouring, not opposite.

Returns a 0-100 Behaviour Similarity score plus the histograms needed for the
24-hour activity chart in the dashboard.
"""

from datetime import datetime

import numpy as np

from utils.helpers import calibrate, cosine, events_of_actor, events_of_persona

HOUR_LOW, HOUR_HIGH = 0.35, 0.985
WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday",
                 "Friday", "Saturday", "Sunday"]


def _smooth_circular(vec, passes=1):
    v = np.array(vec, dtype=float)
    for _ in range(passes):
        v = 0.25 * np.roll(v, 1) + 0.5 * v + 0.25 * np.roll(v, -1)
    return v


def profile(events):
    """Build hour / weekday histograms and intensity stats from raw events."""
    hours = np.zeros(24)
    weekdays = np.zeros(7)
    dates = set()
    for e in events:
        hours[int(e["hour"])] += 1
        if e["weekday"] in WEEKDAY_ORDER:
            weekdays[WEEKDAY_ORDER.index(e["weekday"])] += 1
        dates.add(e["date"])
    n = len(events)
    if n:
        span = _span_days(events)
        per_week = n / max(span / 7.0, 1.0)
    else:
        per_week = 0.0
    return {
        "hours": hours.tolist(),
        "hours_norm": (hours / n).tolist() if n else [0.0] * 24,
        "weekdays": weekdays.tolist(),
        "weekdays_norm": (weekdays / n).tolist() if n else [0.0] * 7,
        "event_count": n,
        "active_days": len(dates),
        "events_per_week": round(per_week, 2),
        "peak_hours": sorted(range(24), key=lambda h: -hours[h])[:3] if n else [],
    }


def _span_days(events):
    ds = [datetime.strptime(e["date"], "%Y-%m-%d") for e in events]
    return max((max(ds) - min(ds)).days, 1)


def analyse(ds, subject_id, actor_id, min_events=4):
    subj_events = events_of_persona(ds, subject_id)
    act_events = events_of_actor(ds, actor_id)
    if len(subj_events) < min_events or len(act_events) < min_events:
        return {"score": None, "available": False, "evidence": [],
                "reason": "insufficient activity events for a rhythm comparison"}

    sp, ap = profile(subj_events), profile(act_events)

    hour_sim = cosine(_smooth_circular(sp["hours_norm"]).tolist(),
                      _smooth_circular(ap["hours_norm"]).tolist())
    wd_sim = cosine(sp["weekdays_norm"], ap["weekdays_norm"])

    # intensity similarity: ratio of posting rates (order-independent)
    a, b = sp["events_per_week"], ap["events_per_week"]
    intensity = min(a, b) / max(a, b) if max(a, b) > 0 else 0.0

    hour_c = calibrate(hour_sim, HOUR_LOW, HOUR_HIGH)
    wd_c = calibrate(wd_sim, 0.55, 1.0)
    score = round(0.60 * hour_c + 0.25 * wd_c + 0.15 * intensity * 100, 1)

    evidence = [
        {"type": "hourly_rhythm",
         "detail": f"peak hours {sp['peak_hours']} vs {ap['peak_hours']} "
                   f"(cosine {hour_sim:.3f})",
         "weight": round(hour_sim, 3)},
        {"type": "weekday_rhythm",
         "detail": f"weekday distribution cosine {wd_sim:.3f}",
         "weight": round(wd_sim, 3)},
        {"type": "posting_intensity",
         "detail": f"{sp['events_per_week']}/week vs {ap['events_per_week']}/week",
         "weight": round(intensity, 3)},
    ]

    return {
        "score": score,
        "available": True,
        "evidence": evidence,
        "components": {"hour_cosine": round(hour_sim, 4),
                       "weekday_cosine": round(wd_sim, 4),
                       "intensity_ratio": round(intensity, 4)},
        "subject_profile": sp,
        "actor_profile": ap,
    }
