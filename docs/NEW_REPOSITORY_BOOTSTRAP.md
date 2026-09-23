# New Repository Bootstrap

Status: ready for repository creation  
Date: 2026-09-22

## Target

Working repository name:

ngallodev-software/agent-workflow-herdr

The final product name may change after the workflow-engine decision gate. Do not rename the Python package or publish a new distribution until that decision is made.

## Authoritative origin

Source repository:

ngallodev-software/agent-workflow

Fork point:

63627e6ec73fa62c18da64ffc38c5189cced6458

Fork-point commit message:

Test sealed-provenance cross-run verification path

Source release line:

0.11.6

Planning branch created after the fork point:

herdr-overhaul-bootstrap

The planning branch contains research and migration documentation only. The new implementation should preserve the original Git history so individual retained invariants can be traced back to their source implementation and tests.

## Repository-creation constraint

The GitHub integration used for this planning work exposes branch, file, tree, commit, issue, and pull-request operations, but it does not expose repository creation/fork/import.

Therefore the one required manual step is:

1. Create an empty repository named agent-workflow-herdr under ngallodev-software.

Do not initialize it with a README, license, or .gitignore if the full source history will be pushed into it.

After the empty repository exists, seed it from the planning branch.

## Preferred history-preserving bootstrap

From an existing clean clone of agent-workflow:

~~~bash
git fetch origin
git checkout herdr-overhaul-bootstrap

git remote rename origin upstream
git remote add origin git@github.com:ngallodev-software/agent-workflow-herdr.git

git push -u origin herdr-overhaul-bootstrap:main
~~~

This produces a new repository whose main branch contains:

- the complete original history through 0.11.6;
- the Herdr overhaul planning commits;
- no implementation deletion yet.

Keep the original repository configured as upstream:

~~~bash
git remote -v

# expected
origin    git@github.com:ngallodev-software/agent-workflow-herdr.git
upstream  <original agent-workflow remote>
~~~

If HTTPS authentication is preferred, use the existing authenticated HTTPS remote form rather than introducing a credential helper or token into scripts.

## Alternative bootstrap from a fresh clone

~~~bash
git clone https://github.com/ngallodev-software/agent-workflow.git agent-workflow-herdr
cd agent-workflow-herdr

git checkout herdr-overhaul-bootstrap
git remote rename origin upstream
git remote add origin https://github.com/ngallodev-software/agent-workflow-herdr.git
git push -u origin herdr-overhaul-bootstrap:main
~~~

Use the user's existing GitHub authentication. No bootstrap script should attempt to manufacture credentials.

## Initial branch policy in the new repository

main
: Research-approved architecture baseline and eventually the stable replacement.

research/*
: Prior-art experiments, Herdr capability verification, dependency evaluation.

phase/*
: Implementation phases after the architecture gate.

benchmark/*
: Comparative benchmarks against Agent-Workflow 0.11.6.

Do not merge broad implementation work directly into main until the Phase 0 decision gates are closed.

## Files that should exist immediately

The new repository should initially contain these fork-specific records:

- docs/HERDR_OVERHAUL_MASTER_PLAN.md
- docs/HERDR_PRIOR_ART.md
- docs/HERDR_CAPABILITY_MATRIX.md
- docs/NEW_REPOSITORY_BOOTSTRAP.md
- docs/DECISIONS/DEC-010-HERDR-CENTERED-FORK.md

The current 0.11.6 code remains present at bootstrap only as source material. Presence does not imply that a module is approved for porting into the replacement architecture.

## First change after repository creation

Create a Phase 0 branch and classify every production module as:

- retain;
- extract/simplify;
- replace with Herdr;
- replace with plugin;
- compatibility-only;
- delete;
- decision-gated.

No functional deletion should precede this inventory because it will become the traceable migration map.

## Dependency policy

The new repository should not immediately add all interesting Herdr plugins as dependencies.

Use three classes:

### Required platform dependency

Herdr itself, at a minimum version selected after live capability verification.

### Core library dependency

Allowed only when the dependency becomes part of workflow correctness. It must pass license, maturity, replay, failure, and compatibility review.

### Optional operator integration

Review UI, DAG UI, notification, progress, token dashboard, worktree setup, task board, and similar plugins. The core should detect or integrate with them without requiring them for correctness.

## Versioning

The new repository should not continue directly as 0.11.7.

Recommended pre-release sequence:

- 0.1.0-alpha.1: evidence kernel extracted;
- 0.1.0-alpha.2: Herdr execution adapter;
- 0.1.0-alpha.3: workflow engine/reducer path;
- 0.1.0-beta.1: feature-complete acceptance journeys;
- 1.0.0 only after the new architecture is the recommended line.

The old 0.11.x version numbers continue to identify the original implementation.

## Migration rule

The old repository is not deprecated at repository creation.

Deprecation requires:

- equivalent protected acceptance journeys;
- lower measured orchestration overhead;
- stable Herdr integration;
- restart/replay evidence;
- migration documentation;
- at least one complete real-project benchmark.

Until then:

~~~
agent-workflow       = stable/reference implementation
agent-workflow-herdr = experimental replacement
~~~

## Immediate handoff

Once the empty target repository exists, seed main from herdr-overhaul-bootstrap, verify the fork-point history, and continue all overhaul implementation in the new repository.
