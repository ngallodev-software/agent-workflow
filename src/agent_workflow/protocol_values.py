"""Authoritative finite values for worker and lifecycle protocol choices.

Keep protocol vocabulary in one place so CLI parsers, deterministic builders,
and semantic validation cannot silently drift apart.
"""

COMPLETION_RESULTS = ("completed", "partial", "failed", "blocked")
CRITERION_RESULTS = ("pass", "fail", "not_verified")
REVIEW_DISPOSITIONS = ("approved", "changes_requested", "blocked")
ACKNOWLEDGEMENT_OUTCOMES = ("applied", "rejected")
