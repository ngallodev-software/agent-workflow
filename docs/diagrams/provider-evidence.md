# Provider Evidence

``` mermaid
flowchart LR
  Raw[Stable regular non-symlink raw JSONL] --> Capture[Bounded parse + complete hash]
  Capture --> Identity[Provider event identity / duplicate ambiguity]
  Identity --> Mode{delta/cumulative/terminal}
  Mode --> Merge[Fail-closed finite and monotonic merge]
  Merge --> Evidence[provider-evidence.json]
  Evidence --> Seal[final receipt]
  Seal --> Scores[Validate content-addressed score receipts]
  Scores --> Trial[trial evidence]
  ```
