# HERDR-GATE-0 — boundary inventory review

Independently inspect the complete HERDR-001 inventory and both repository
baselines. Accept only when every tmux/pane caller has an owner, durable versus
presentation authority is explicit, Herdr APIs are verified from source/docs,
and later writable scopes are disjoint. Otherwise reject with typed findings;
do not implement migration work in the gate.
