"""Metric suppression — muting a noisy metric without deleting it.

A metric that fires every day trains people to ignore the whole feed, which is
worse than the metric being wrong. Suppression takes it out of the insight feed
and out of the analysis pass, while leaving its history and definition intact.

The expiry is an absolute timestamp rather than a duration. Storing "snoozed for
7 days" would restart the clock every time it was read; storing the moment it
lapses cannot. A lapsed suppression simply stops matching, so the metric returns
on its own with no cleanup job.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.models import Metric

# A snooze longer than this is almost certainly someone burying a real problem.
MAX_SNOOZE_DAYS = 90


def is_suppressed(metric: Metric, now: datetime | None = None) -> bool:
    """True when the metric is currently muted."""
    if metric.suppressed_at is None:
        return False
    if metric.suppressed_until is None:
        # Indefinite: muted until someone explicitly restores it.
        return True
    return metric.suppressed_until > (now or datetime.utcnow())


def suppress(
    metric: Metric,
    days: float | None = None,
    reason: str | None = None,
    now: datetime | None = None,
) -> Metric:
    """Mute a metric, optionally for a fixed number of days.

    `days=None` mutes indefinitely. Raises for a non-positive or over-long
    window rather than silently clamping, so a bad call is visible.
    """
    moment = now or datetime.utcnow()

    if days is not None:
        if days <= 0:
            raise ValueError("days must be positive")
        if days > MAX_SNOOZE_DAYS:
            raise ValueError(f"days must be at most {MAX_SNOOZE_DAYS}")

    metric.suppressed_at = moment
    metric.suppressed_until = None if days is None else moment + timedelta(days=days)
    metric.suppression_reason = (reason or "").strip() or None
    return metric


def restore(metric: Metric) -> Metric:
    """Bring a metric back into the feed immediately."""
    metric.suppressed_at = None
    metric.suppressed_until = None
    metric.suppression_reason = None
    return metric


def active_metrics(metrics: list[Metric], now: datetime | None = None) -> list[Metric]:
    """The metrics the analysis pass and the feed should consider."""
    moment = now or datetime.utcnow()
    return [m for m in metrics if not is_suppressed(m, moment)]
