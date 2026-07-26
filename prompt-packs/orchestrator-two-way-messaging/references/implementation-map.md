# Implementation map

This map is directional. Agents must inspect current source before choosing exact modules.

| Surface | Likely current modules | Planned extension |
|---|---|---|
| Per-session durable records | `messages.py`, `sessions.py`, `agent_context.py` | Durable consumer cursors, handling dispositions, stable source identity. |
| Wake hints | `tmux.py` | Shared orchestrator channel derived from non-sensitive identity. |
| Aggregate delivery | New orchestrator inbox/registry service | Append-only normalized events and acknowledgements. |
| Supervisor | New foregroundable service plus CLI dispatch | Replay/fan-in loop, single-owner lock, bounded wait/backoff. |
| Orchestrator resume | Executor/tmux adapter boundary | Fixed opaque notification, start/resume outcome evidence. |
| Late child steering | Executor adapters plus message services | Delivered/applied/rejected result tied to correlation ID. |
| Scheduling decisions | Workflow/session services | Action evidence references resulting assignment/lifecycle record. |
| Security | Shared hardening substrates | Principal binding, redaction, bounds, no-follow, rate/retention policy. |
| Acceptance | `tests/acceptance`, `tests/live`, deterministic fixtures | Public installed-product journeys and opt-in real tmux/provider compatibility. |

Do not create a second scheduler, second lifecycle journal, or alternate message store for existing per-session authority.
