# Delegation Lifecycle

## Prepare

- validate the pack;
- confirm ticket dependencies;
- create a clean isolated worktree;
- choose a unique session name;
- capture source revision and branch.

## Launch

The immutable prompt copy, command argv, prompt hash, and source baseline are stored before tmux starts. A failed launch is recorded rather than silently discarded.

## Observe

Use `status`, `attach`, and `tail`. The operator can always bring the terminal to the foreground. A likely stall is an observation requiring human classification.

## Interrupt and retry

Interrupt first. Preserve the original run directory and worktree. A retry uses `-retryN`, copies the original prompt and command, and links back through `retry_of`.

## Complete

The implementer fills in the generated completion report. The reviewer inspects the diff and reruns narrow gates independently. The original session record remains evidence after branch merge or worktree removal.
