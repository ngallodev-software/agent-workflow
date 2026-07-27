# Orchestrator

##

### Two-Way messaging dependencies

``` mermaid
flowchart TD
    DEC[DEC-001 durable-control SLO] --> BKL1[BKL-001 durable consumer cursors]
    HARD2[HARD-002 path and artifact integrity] --> BKL1
    HARD4[HARD-004 immutable launch authority] --> BKL1

    DEC --> MSG1[MSG-001 registry and durable inbox]
    HARD2 --> MSG1
    HARD4 --> MSG1

    BKL1 --> MSG2[MSG-002 supervisor and shared wake channel]
    MSG1 --> MSG2
    HARD1[HARD-001 bounded process substrate] --> MSG2
    HARD8[HARD-008 config and executor trust] --> MSG2

    BKL1 --> BKL2[BKL-002 executor late steering]
    HARD1 --> BKL2
    HARD4 --> BKL2
    HARD7[HARD-007 authenticated principals] --> BKL2

    MSG2 --> MSG3[MSG-003 safe orchestrator wake/resume adapters]
    HARD4 --> MSG3
    HARD6[HARD-006 sensitive-content controls] --> MSG3
    HARD7 --> MSG3

    BKL1 --> MSG5[MSG-005 restart reconstruction]
    MSG1 --> MSG5
    MSG2 --> MSG5

    MSG2 --> MSG4[MSG-004 delivery/application/action evidence]
    MSG3 --> MSG4
    MSG5 --> MSG4
    HARD7 --> MSG4

    BKL2 --> MSG6[MSG-006 messaging security hardening]
    MSG1 --> MSG6
    MSG2 --> MSG6
    MSG3 --> MSG6
    MSG4 --> MSG6
    MSG5 --> MSG6

    BKL2 --> MSG7[MSG-007 acceptance and live compatibility]
    MSG1 --> MSG7
    MSG2 --> MSG7
    MSG3 --> MSG7
    MSG4 --> MSG7
    MSG5 --> MSG7

    MSG6 --> GATE[MSG-GATE-01 independent review]
    MSG7 --> GATE
```
