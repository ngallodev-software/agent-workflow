"""Authoritative finite values for Agent-Workflow protocol choices.

Keep administrative vocabulary in one place so CLI parsers, deterministic
builders, state-transition operations, and schemas cannot silently drift apart.
"""

COMPLETION_RESULTS = ("completed", "partial", "failed", "blocked")
CRITERION_RESULTS = ("pass", "fail", "not_verified")
REVIEW_DISPOSITIONS = ("approved", "changes_requested", "blocked")
ACKNOWLEDGEMENT_OUTCOMES = ("applied", "rejected")
LIFECYCLE_ACTIONS = ("reviewed", "accepted", "rejected")
PREREQUISITE_REQUIREMENTS = ("accepted", "sealed_completed")
ASSIGNMENT_STATES = ("busy", "closed")
ASSIGNMENT_EVENTS = ("task_completed",)
