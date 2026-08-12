"""
Time helper - Final optimization (Phase 14).

datetime.utcnow() is deprecated in Python 3.12+ in favor of
datetime.now(timezone.utc), but that returns a timezone-*aware*
datetime, which doesn't match MySQL's tz-naive DATETIME columns
(binding an aware datetime to them can behave inconsistently across
drivers). utcnow() here gives the same naive-UTC value
datetime.utcnow() used to, without the deprecation warning - use it
anywhere a db.Column(default=...) or plain "now" value used to call
datetime.utcnow() directly.
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
