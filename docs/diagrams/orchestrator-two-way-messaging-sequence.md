# Orchestrator

## Two-Way messaging sequence

``` mermaid
sequenceDiagram
    participant C as Child agent
    participant CL as Child message log
    participant OI as Orchestrator inbox
    participant S as Python supervisor
    participant T as tmux wake channel
    participant O as Orchestrator agent

    C->>CL: append task_complete + fsync
    C-->>T: signal shared orchestrator channel
    S->>T: bounded wait
    T-->>S: wake hint
    S->>CL: replay after durable child cursor
    S->>OI: append normalized child_idle event + fsync
    S->>S: validate, deduplicate, classify
    S->>O: inject fixed notification containing event ID
    O->>OI: read validated event by ID
    O->>OI: append orchestrator_ack
    O->>CL: append new steer or assignment
    O-->>T: signal child channel
```
