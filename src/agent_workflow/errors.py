class WorkflowError(RuntimeError):
    """Expected operational error displayed without a traceback."""


class InteractiveCapacityError(WorkflowError):
    """An interactive launch needs an explicit pane-cap decision."""

    def __init__(self, *, count: int, maximum: int, idle_sessions: list[dict]):
        self.count = count
        self.maximum = maximum
        self.idle_sessions = idle_sessions
        self.required_closures = max(1, count - maximum + 1)
        names = ", ".join(
            str(item.get("agent_name") or item.get("session_id"))
            for item in idle_sessions
        ) or "none"
        super().__init__(
            f"interactive agent pane limit reached: {count}/{maximum}; "
            f"idle panes: {names}; choose close-idle, non-interactive, or cancel"
        )

    def as_dict(self) -> dict:
        return {
            "error": "interactive_pane_limit",
            "count": self.count,
            "maximum": self.maximum,
            "required_closures": self.required_closures,
            "idle_sessions": self.idle_sessions,
            "choices": ["close-idle", "non-interactive", "cancel"],
        }
