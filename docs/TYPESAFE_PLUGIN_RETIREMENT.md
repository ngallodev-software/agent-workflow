# TypeSafe plugin retirement

`agent-workflow-typesafe-ai` is retired as a separately deployed Agent-Workflow plugin beginning with the integrated 0.11.x source line.

Its Agent-Workflow-specific routing capability now lives behind the host-owned decision boundary as the optional `agent-workflow[typesafe]` feature. Generic external plugin support is unchanged. Historical provider-namespaced comparative evidence remains readable through `agent-workflow-comparative-eval`; those schema IDs are compatibility history, not an active plugin dependency.

Migration:

1. remove `agent-workflow-typesafe` from `[plugins].enabled`;
2. install `agent-workflow[typesafe]` when live semantic decisions are wanted;
3. keep `TYPESAFE_API_KEY` in the runtime environment;
4. move model/log settings to `[semantic.typesafe]`;
5. select `deterministic`, `typesafe`, or `comparative` through `[decision_policy].mode`.
